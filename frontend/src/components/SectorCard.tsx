import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { Fragment, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";

import { Card, CardHeader, ErrorState, Notice, SkeletonRows } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/form";
import { api, type ClassCount, type FlightRef, type I034, type SectorDetail, type Status } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const wholeNumber = /^\d+$/;

const schema = z
  .object({
    classes: z.array(
      z.object({
        slot: z.string(),
        code: z.string().trim().max(3, "At most 3 characters"),
        pax: z.string().trim().refine((v) => v === "" || wholeNumber.test(v), "Enter a whole number"),
      }),
    ),
    meals: z.array(
      z.object({
        class_code: z
          .string()
          .trim()
          .min(1, "Enter a class")
          .max(3, "At most 3 characters")
          .regex(/^[PJSY]/i, "Starts with P, J, S or Y"),
        meal_type: z.string().trim().max(2, "At most 2 characters"),
        spml_id: z.string().trim().min(1, "Enter a code").max(40, "At most 40 characters"),
        qnty: z.string().trim().regex(wholeNumber, "Enter a whole number"),
        pname: z.string().nullable(),
        meal_nr: z.string().nullable(),
        txt: z.string().nullable(),
      }),
    ),
  })
  .superRefine((value, ctx) => {
    const seen = new Set<string>();
    value.meals.forEach((m, index) => {
      const key = [m.class_code, m.meal_type, m.spml_id].map((s) => s.trim().toUpperCase()).join("|");
      if (seen.has(key)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["meals", index, "spml_id"],
          message: "This class, meal type and code is already listed",
        });
      }
      seen.add(key);
    });
  });

type FormValues = z.infer<typeof schema>;

function toForm(sector: SectorDetail): FormValues {
  return {
    classes: sector.i033.classes.map((c) => ({
      slot: c.slot,
      code: c.code ?? "",
      pax: c.pax === null ? "" : String(c.pax),
    })),
    meals: sector.i034.map((m) => ({
      class_code: m.class_code,
      meal_type: m.meal_type ?? "",
      spml_id: m.spml_id,
      qnty: String(m.qnty),
      pname: m.pname,
      meal_nr: m.meal_nr,
      txt: m.txt,
    })),
  };
}

const slotLabel = (slot: string) => slot.toUpperCase().replace("_", " ");

const SLOT_GROUPS: [string, string[]][] = [
  ["First", ["p"]],
  ["Business", ["jm", "ju", "jf", "ja"]],
  ["Premium economy", ["sm", "su", "sf", "sa"]],
  ["Economy", ["yu", "yf", "ya", "y"]],
  ["Crew", ["staff_p", "staff_j", "staff_s", "staff_y"]],
];

/** The slots grouped by cabin. A slot the groups do not know still gets a field. */
function slotGroups(slots: string[]): [string, string[]][] {
  const known = new Set(SLOT_GROUPS.flatMap(([, g]) => g));
  const groups = SLOT_GROUPS.map(([name, g]): [string, string[]] => [name, g.filter((x) => slots.includes(x))]);
  const other = slots.filter((x) => !known.has(x));
  if (other.length) groups.push(["Other", other]);
  return groups.filter(([, g]) => g.length > 0);
}

function ClassesTable({ classes }: { classes: ClassCount[] }) {
  const filled = classes.filter((c) => c.pax !== null);
  if (filled.length === 0) {
    return <p className="text-sm text-content-muted">No pax counts on this version</p>;
  }
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th scope="col">Class slot</th>
          <th scope="col">Code</th>
          <th scope="col" className="text-right">
            Pax
          </th>
        </tr>
      </thead>
      <tbody>
        {filled.map((c) => (
          <tr key={c.slot}>
            <td className="num">{slotLabel(c.slot)}</td>
            <td className="num">{c.code}</td>
            <td className="num text-right">{c.pax}</td>
          </tr>
        ))}
        <tr>
          <td className="font-semibold" colSpan={2}>
            Total
          </td>
          <td className="num text-right font-semibold">{filled.reduce((sum, c) => sum + (c.pax ?? 0), 0)} pax</td>
        </tr>
      </tbody>
    </table>
  );
}

function MealsTable({ meals }: { meals: I034[] }) {
  if (meals.length === 0) {
    return <p className="text-sm text-content-muted">No special meals on this version</p>;
  }
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th scope="col">Class</th>
          <th scope="col">Meal type</th>
          <th scope="col">Code</th>
          <th scope="col" className="text-right">
            Qty
          </th>
        </tr>
      </thead>
      <tbody>
        {meals.map((m) => (
          <tr key={m.i034_id}>
            <td className="num">{m.class_code}</td>
            <td className="num">{m.meal_type}</td>
            <td className="num">{m.spml_id}</td>
            <td className="num text-right">{m.qnty}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? (
    <p id={id} className="pt-xxs text-xs text-content-primary">
      <span className="font-semibold text-status-error">Fix: </span>
      {message}
    </p>
  ) : null;
}

function VersionDialog({
  flight,
  status,
  sector,
  version,
  onClose,
}: {
  flight: FlightRef;
  status: Status;
  sector: number;
  version: number;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: ["version", flight, status, sector, version],
    queryFn: () => api.version(flight, status, sector, version),
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={`Version ${version}`}
        description={
          query.data
            ? `${query.data.i033.created_source === "USER" ? "Edited by" : "Extracted by"} ` +
              `${query.data.i033.created_by}, ${formatDateTime(query.data.i033.created_at)}`
            : `Sector ${sector}, ${status}`
        }
        className="max-w-2xl"
      >
        {query.isPending ? (
          <SkeletonRows />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : (
          <div className="flex flex-col gap-md">
            <ClassesTable classes={query.data.i033.classes} />
            <MealsTable meals={query.data.i034} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function SectorCard({
  flight,
  status,
  sector,
  locked,
  showSectorNumber,
  onSaved,
}: {
  flight: FlightRef;
  status: Status;
  sector: SectorDetail;
  locked: boolean;
  showSectorNumber: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [viewVersion, setViewVersion] = useState<number | null>(null);
  const n = sector.sector_nbr;

  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: toForm(sector) });
  const meals = useFieldArray({ control: form.control, name: "meals" });
  const errors = form.formState.errors;

  const save = useMutation({
    mutationFn: (values: FormValues) =>
      api.saveSector(flight, status, n, {
        base_version_no: sector.i033.version_no,
        classes: values.classes.map((c) => ({
          slot: c.slot,
          code: c.code.trim().toUpperCase() || null,
          pax: c.pax.trim() === "" ? null : Number(c.pax),
        })),
        i034: values.meals.map((m) => ({
          class_code: m.class_code.trim().toUpperCase(),
          meal_type: m.meal_type.trim().toUpperCase() || null,
          spml_id: m.spml_id.trim().toUpperCase(),
          qnty: Number(m.qnty),
          pname: m.pname,
          meal_nr: m.meal_nr,
          txt: m.txt,
        })),
      }),
    onSuccess: (result) => {
      setWarnings(result.warnings);
      setEditing(false);
      onSaved();
    },
  });

  const startEdit = () => {
    form.reset(toForm(sector));
    save.reset();
    setWarnings([]);
    setEditing(true);
  };

  const title = showSectorNumber ? `Sector ${n}` : "Pax and special meals";
  const meta =
    `Version ${sector.i033.version_no}, ` +
    `${sector.i033.created_source === "USER" ? "edited by" : "extracted by"} ${sector.i033.created_by}, ` +
    formatDateTime(sector.i033.created_at);

  return (
    <Card>
      <CardHeader
        title={title}
        meta={meta}
        actions={
          editing || locked ? undefined : (
            <Button variant="secondary" onClick={startEdit}>
              <Pencil strokeWidth={1.75} /> Edit
            </Button>
          )
        }
      />

      {warnings.length > 0 ? (
        <div className="mb-md">
          <Notice tone="warning" title="Saved with a warning">
            <ul className="list-disc pl-md">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </Notice>
        </div>
      ) : null}

      {!editing ? (
        <div className="grid gap-lg xl:grid-cols-2">
          <div className="flex flex-col gap-xs">
            <h4 className="text-sm font-semibold">Pax by class (I033)</h4>
            <ClassesTable classes={sector.i033.classes} />
          </div>
          <div className="flex flex-col gap-xs">
            <h4 className="text-sm font-semibold">Special meals (I034)</h4>
            {sector.i033.is_ex_sector ? (
              <p className="text-sm text-content-muted">Ex-sector uplift: pax counts only, no special meals</p>
            ) : (
              <MealsTable meals={sector.i034} />
            )}
          </div>
        </div>
      ) : (
        <form onSubmit={form.handleSubmit((values) => save.mutate(values))} noValidate className="flex flex-col gap-md">
          <div className="flex flex-col gap-lg">
            <div className="flex flex-col gap-xs">
              <h4 className="text-sm font-semibold">Pax by class (I033)</h4>
              <p className="text-xs text-content-muted">Each class slot takes a class code and a pax count</p>
              {/* One block per cabin, so the slots line up in short columns instead of one
                  wide grid that overflows its cell. */}
              <div className="grid items-start gap-md sm:grid-cols-2">
                {slotGroups(form.getValues("classes").map((c) => c.slot)).map(([name, slots]) => (
                  <fieldset key={name} className="flex min-w-0 flex-col gap-xs rounded-md border p-sm">
                    <legend className="px-xxs text-xs font-semibold text-content-secondary">{name}</legend>
                    <div className="grid grid-cols-[64px_minmax(0,1fr)_minmax(0,1fr)] items-center gap-x-xs gap-y-xs">
                      <span className="text-xs text-content-muted">Slot</span>
                      <span className="text-xs text-content-muted">Code</span>
                      <span className="text-xs text-content-muted">Pax</span>
                      {slots.map((slot) => {
                        const i = form.getValues("classes").findIndex((c) => c.slot === slot);
                        return (
                          <Fragment key={slot}>
                            <span className="num text-xs font-semibold text-content-secondary">{slotLabel(slot)}</span>
                            <Input
                              aria-label={`${slotLabel(slot)} class code`}
                              aria-invalid={Boolean(errors.classes?.[i]?.code)}
                              aria-describedby={`s${n}-c${i}-code`}
                              className="num w-full uppercase"
                              maxLength={3}
                              {...form.register(`classes.${i}.code`)}
                            />
                            <Input
                              aria-label={`${slotLabel(slot)} pax`}
                              aria-invalid={Boolean(errors.classes?.[i]?.pax)}
                              aria-describedby={`s${n}-c${i}-pax`}
                              inputMode="numeric"
                              className="num w-full"
                              {...form.register(`classes.${i}.pax`)}
                            />
                            <div className="col-span-3 empty:hidden">
                              <FieldError id={`s${n}-c${i}-code`} message={errors.classes?.[i]?.code?.message} />
                              <FieldError id={`s${n}-c${i}-pax`} message={errors.classes?.[i]?.pax?.message} />
                            </div>
                          </Fragment>
                        );
                      })}
                    </div>
                  </fieldset>
                ))}
              </div>
            </div>

            <div className="flex min-w-0 flex-col gap-xs">
              <h4 className="text-sm font-semibold">Special meals (I034)</h4>
              {sector.i033.is_ex_sector ? (
                <p className="text-sm text-content-muted">Ex-sector uplift: pax counts only, no special meals</p>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="tbl">
                      <thead>
                        <tr>
                          <th scope="col">Class</th>
                          <th scope="col">Meal type</th>
                          <th scope="col">Code</th>
                          <th scope="col">Qty</th>
                          <th scope="col">
                            <span className="sr-only">Remove</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {meals.fields.map((field, i) => {
                          const e = errors.meals?.[i];
                          const id = `s${n}-m${i}`;
                          return (
                            <tr key={field.id}>
                              <td className="align-top">
                                <Input
                                  aria-label={`Line ${i + 1} class`}
                                  aria-invalid={Boolean(e?.class_code)}
                                  aria-describedby={`${id}-class`}
                                  className="num w-[72px] uppercase placeholder:normal-case"
                                  maxLength={3}
                                  {...form.register(`meals.${i}.class_code`)}
                                />
                                <FieldError id={`${id}-class`} message={e?.class_code?.message} />
                              </td>
                              <td className="align-top">
                                <Input
                                  aria-label={`Line ${i + 1} meal type`}
                                  aria-invalid={Boolean(e?.meal_type)}
                                  aria-describedby={`${id}-type`}
                                  className="num w-[64px] uppercase"
                                  maxLength={2}
                                  {...form.register(`meals.${i}.meal_type`)}
                                />
                                <FieldError id={`${id}-type`} message={e?.meal_type?.message} />
                              </td>
                              <td className="align-top">
                                <Input
                                  aria-label={`Line ${i + 1} special meal code`}
                                  aria-invalid={Boolean(e?.spml_id)}
                                  aria-describedby={`${id}-code`}
                                  className="num min-w-[120px] uppercase"
                                  maxLength={40}
                                  {...form.register(`meals.${i}.spml_id`)}
                                />
                                <FieldError id={`${id}-code`} message={e?.spml_id?.message} />
                              </td>
                              <td className="align-top">
                                <Input
                                  aria-label={`Line ${i + 1} quantity`}
                                  aria-invalid={Boolean(e?.qnty)}
                                  aria-describedby={`${id}-qty`}
                                  inputMode="numeric"
                                  className="num w-[80px]"
                                  {...form.register(`meals.${i}.qnty`)}
                                />
                                <FieldError id={`${id}-qty`} message={e?.qnty?.message} />
                              </td>
                              <td className="align-top">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  aria-label={`Remove line ${i + 1}`}
                                  onClick={() => meals.remove(i)}
                                >
                                  <Trash2 strokeWidth={1.75} />
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        meals.append({
                          class_code: "",
                          meal_type: "",
                          spml_id: "",
                          qnty: "",
                          pname: null,
                          meal_nr: null,
                          txt: null,
                        })
                      }
                    >
                      <Plus strokeWidth={1.75} /> Add special meal
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>

          {save.isError ? (
            <Notice tone="error" title="Not saved">
              {save.error.message}
            </Notice>
          ) : null}

          <div className="flex flex-wrap justify-end gap-xs">
            <Button variant="ghost" onClick={() => setEditing(false)} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving" : "Save as new version"}
            </Button>
          </div>
        </form>
      )}

      {/* Native <details>: a disclosure with keyboard support and no JavaScript. */}
      <details className="mt-md text-sm">
        <summary className="min-h-[44px] cursor-pointer py-sm font-semibold text-content-secondary">
          Version history ({sector.versions.length})
        </summary>
        <table className="tbl">
          <thead>
            <tr>
              <th scope="col">Version</th>
              <th scope="col">Source</th>
              <th scope="col">By</th>
              <th scope="col">Created</th>
              <th scope="col">
                <span className="sr-only">View</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {sector.versions.map((v) => (
              <tr key={v.version_no}>
                <td className="num">
                  {v.version_no}
                  {v.is_current ? <span className="pl-xs text-xs text-content-muted">Current</span> : null}
                </td>
                <td>{v.created_source === "USER" ? "User edit" : "Extraction"}</td>
                <td>{v.created_by}</td>
                <td className="num whitespace-nowrap">{formatDateTime(v.created_at)}</td>
                <td className="text-right">
                  {v.is_current ? null : (
                    <Button variant="ghost" onClick={() => setViewVersion(v.version_no)}>
                      View
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      {viewVersion !== null ? (
        <VersionDialog
          flight={flight}
          status={status}
          sector={n}
          version={viewVersion}
          onClose={() => setViewVersion(null)}
        />
      ) : null}
    </Card>
  );
}

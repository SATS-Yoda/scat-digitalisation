import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowLeftRight, Ban, CheckCircle2, Plus, SlidersHorizontal } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link } from "react-router-dom";

import { Card, EmptyState, ErrorState, Notice, Pill, SkeletonRows } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/form";
import { type AirlineSetting, api, type ReturnFlightMapping } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const code = (value: string) => value.toUpperCase().replace(/[^A-Z0-9]/g, "");

function PageHeader({ title, children }: { title: string; children: ReactNode }) {
  return (
    <header className="flex flex-col gap-xxs">
      <Link to="/admin" className="flex min-h-[44px] w-fit items-center gap-xs text-sm font-medium link">
        <ArrowLeft className="size-4" strokeWidth={1.75} aria-hidden /> Admin settings
      </Link>
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="max-w-3xl text-sm text-content-muted">{children}</p>
    </header>
  );
}

const SETTINGS = [
  {
    to: "/admin/return-flights",
    icon: ArrowLeftRight,
    title: "Return flight mapping",
    text: "Which return flight is sent inside each outbound flight's files, and how many days later it departs.",
  },
  {
    to: "/admin/airline-settings",
    icon: SlidersHorizontal,
    title: "Airline auto-release settings",
    text: "Whether each airline's stages are sent to SAP automatically, and how long to hold them first.",
  },
];

export function AdminSettingsPage() {
  return (
    <>
      <header className="flex flex-col gap-xxs">
        <h1 className="text-2xl font-semibold">Admin settings</h1>
        <p className="max-w-3xl text-sm text-content-muted">Choose which setting to change.</p>
      </header>
      <div className="grid gap-md md:grid-cols-2">
        {SETTINGS.map(({ to, icon: Icon, title, text }) => (
          <Link key={to} to={to} className="block rounded-lg hover:bg-surface-hover">
            <Card className="flex h-full flex-col gap-xs">
              <span className="flex items-center gap-xs text-md font-semibold">
                <Icon className="size-5" strokeWidth={1.75} aria-hidden />
                {title}
              </span>
              <span className="text-sm text-content-secondary">{text}</span>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-xxs">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}

function ActivePill({ active }: { active: boolean }) {
  return active ? (
    <Pill tone="success" icon={CheckCircle2}>
      Active
    </Pill>
  ) : (
    <Pill tone="neutral" icon={Ban}>
      Inactive
    </Pill>
  );
}

export function ReturnFlightsPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["return-flights"], queryFn: api.returnFlights });
  const blank = { airline: "", outbound_flt_nbr: "", return_flt_nbr: "", day_offset: 0, is_active: true };
  const [draft, setDraft] = useState<ReturnFlightMapping>(blank);

  const save = useMutation({
    mutationFn: api.saveReturnFlight,
    onSuccess: () => {
      // The mapping changes how flights are grouped on the dashboard and stage pages.
      queryClient.invalidateQueries({ queryKey: ["return-flights"] });
      queryClient.invalidateQueries({ queryKey: ["flights"] });
      queryClient.invalidateQueries({ queryKey: ["stage"] });
    },
  });

  const add = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(draft, { onSuccess: () => setDraft(blank) });
  };
  const complete = draft.airline.length >= 2 && draft.outbound_flt_nbr && draft.return_flt_nbr;

  return (
    <>
      <PageHeader title="Return flights">
        A return flight is sent inside its outbound flight's files and shown under it on the flight list. Each
        outbound flight has one active return flight.
      </PageHeader>

      <Card className="p-md">
        <form onSubmit={add} className="flex flex-wrap items-end gap-sm">
          <Field id="rf-airline" label="Airline">
            <Input
              id="rf-airline"
              className="num w-[88px]"
              maxLength={3}
              value={draft.airline}
              onChange={(e) => setDraft({ ...draft, airline: code(e.target.value) })}
            />
          </Field>
          <Field id="rf-out" label="Outbound flight number">
            <Input
              id="rf-out"
              className="num w-[160px]"
              maxLength={5}
              value={draft.outbound_flt_nbr}
              onChange={(e) => setDraft({ ...draft, outbound_flt_nbr: code(e.target.value) })}
            />
          </Field>
          <Field id="rf-ret" label="Return flight number">
            <Input
              id="rf-ret"
              className="num w-[160px]"
              maxLength={5}
              value={draft.return_flt_nbr}
              onChange={(e) => setDraft({ ...draft, return_flt_nbr: code(e.target.value) })}
            />
          </Field>
          <Field id="rf-offset" label="Return departs">
            <Select
              id="rf-offset"
              className="w-[160px]"
              value={draft.day_offset}
              onChange={(e) => setDraft({ ...draft, day_offset: Number(e.target.value) })}
            >
              <option value={0}>Same day</option>
              <option value={1}>Next day</option>
            </Select>
          </Field>
          <Button type="submit" disabled={!complete || save.isPending}>
            <Plus strokeWidth={1.75} /> Add mapping
          </Button>
        </form>
        {save.isError ? (
          <div className="pt-sm">
            <Notice tone="error" title="Mapping not saved">
              {save.error.message}
            </Notice>
          </div>
        ) : null}
      </Card>

      <Card className="overflow-hidden p-0">
        {query.isPending ? (
          <div className="p-lg">
            <SkeletonRows />
          </div>
        ) : query.isError ? (
          <div className="p-lg">
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          </div>
        ) : query.data.length === 0 ? (
          <EmptyState icon={ArrowLeftRight} title="No return flights mapped">
            Add a mapping above for each outbound flight that also caters its return sector, for example SQ 856
            with SQ 857.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Outbound flight</th>
                  <th scope="col">Return flight</th>
                  <th scope="col">Return departs</th>
                  <th scope="col">Status</th>
                  <th scope="col">Last changed</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {query.data.map((m) => (
                  <tr key={`${m.airline}-${m.return_flt_nbr}`}>
                    <td className="num font-semibold">
                      {m.airline} {m.outbound_flt_nbr}
                    </td>
                    <td className="num font-semibold">
                      {m.airline} {m.return_flt_nbr}
                    </td>
                    <td>{m.day_offset === 1 ? "Next day" : "Same day"}</td>
                    <td>
                      <ActivePill active={m.is_active} />
                    </td>
                    <td className="whitespace-nowrap text-content-secondary">
                      <span className="num">{formatDateTime(m.updated_at ?? null)}</span> by {m.updated_by}
                    </td>
                    <td className="text-right">
                      <Button
                        variant="secondary"
                        disabled={save.isPending}
                        onClick={() => save.mutate({ ...m, is_active: !m.is_active })}
                      >
                        {m.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

function SettingRow({ setting, onSave, saving }: { setting: AirlineSetting; onSave: (s: AirlineSetting) => void; saving: boolean }) {
  const [hold, setHold] = useState(String(setting.auto_release_hold_min));
  const holdValid = /^\d+$/.test(hold) && Number(hold) <= 1440;
  const changed = holdValid && Number(hold) !== setting.auto_release_hold_min;
  const id = `hold-${setting.airline}`;
  return (
    <tr>
      <td className="num font-semibold">{setting.airline}</td>
      <td>
        {setting.auto_release ? (
          <Pill tone="info" icon={CheckCircle2}>
            Automatic
          </Pill>
        ) : (
          <Pill tone="neutral" icon={Ban}>
            Manual
          </Pill>
        )}
      </td>
      <td>
        <div className="flex items-center gap-xs">
          <Input
            aria-label={`${setting.airline} hold time in minutes`}
            aria-invalid={!holdValid}
            aria-describedby={`${id}-error`}
            inputMode="numeric"
            className="num w-[96px]"
            value={hold}
            onChange={(e) => setHold(e.target.value)}
          />
          <span className="text-content-secondary">min</span>
        </div>
        {holdValid ? null : (
          <p id={`${id}-error`} className="pt-xxs text-xs">
            <span className="font-semibold text-status-error">Fix: </span>Enter 0 to 1440 minutes
          </p>
        )}
      </td>
      <td className="whitespace-nowrap text-content-secondary">
        <span className="num">{formatDateTime(setting.updated_at ?? null)}</span> by {setting.updated_by}
      </td>
      <td>
        <div className="flex flex-wrap justify-end gap-xs">
          <Button
            variant="secondary"
            disabled={!changed || saving}
            onClick={() => onSave({ ...setting, auto_release_hold_min: Number(hold) })}
          >
            Save hold time
          </Button>
          <Button
            variant="secondary"
            disabled={saving}
            onClick={() => onSave({ ...setting, auto_release: !setting.auto_release })}
          >
            {setting.auto_release ? "Switch to manual" : "Switch to automatic"}
          </Button>
        </div>
      </td>
    </tr>
  );
}

export function AirlineSettingsPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["airline-settings"], queryFn: api.airlineSettings });
  const [airline, setAirline] = useState("");
  const save = useMutation({
    mutationFn: api.saveAirlineSetting,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["airline-settings"] }),
  });

  const add = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(
      { airline, auto_release: false, auto_release_hold_min: 60 },
      { onSuccess: () => setAirline("") },
    );
  };

  return (
    <>
      <PageHeader title="Airline settings">
        Controls whether an airline's flights are sent to SAP automatically, and how long a clean extraction waits
        before it is sent. Airlines not listed here are released manually.
      </PageHeader>

      <Notice tone="info" title="Automatic release is not running yet">
        These settings are stored, but the scheduled release that reads them has not been built. Every flight is
        still sent manually.
      </Notice>

      <Card className="p-md">
        <form onSubmit={add} className="flex flex-wrap items-end gap-sm">
          <Field id="as-airline" label="Airline">
            <Input
              id="as-airline"
              className="num w-[88px]"
              maxLength={3}
              value={airline}
              onChange={(e) => setAirline(code(e.target.value))}
            />
          </Field>
          <Button type="submit" disabled={airline.length < 2 || save.isPending}>
            <Plus strokeWidth={1.75} /> Add airline
          </Button>
        </form>
        {save.isError ? (
          <div className="pt-sm">
            <Notice tone="error" title="Setting not saved">
              {save.error.message}
            </Notice>
          </div>
        ) : null}
      </Card>

      <Card className="overflow-hidden p-0">
        {query.isPending ? (
          <div className="p-lg">
            <SkeletonRows />
          </div>
        ) : query.isError ? (
          <div className="p-lg">
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          </div>
        ) : query.data.length === 0 ? (
          <EmptyState icon={SlidersHorizontal} title="No airline settings">
            Every airline is released manually. Add an airline above to give it a hold time or switch it to
            automatic release.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th scope="col">Airline</th>
                  <th scope="col">Release</th>
                  <th scope="col">Hold time</th>
                  <th scope="col">Last changed</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {query.data.map((s) => (
                  <SettingRow
                    key={`${s.airline}-${s.auto_release_hold_min}`}
                    setting={s}
                    saving={save.isPending}
                    onSave={(next) => save.mutate(next)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

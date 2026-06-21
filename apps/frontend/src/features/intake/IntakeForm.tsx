// Household intake form (F19). One clean card emitting the frozen `Household`
// shape. The street field doubles as a Mapbox address autocomplete: picking a
// suggestion fills street/house_no/plz/city and flies the globe (via onAddressPick).
// Styling follows data/style.md (light SaaS card); motion follows emil-design-eng.
import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState, useId } from "react";
import { type FieldErrors, type UseFormRegister, useForm } from "react-hook-form";
import type { Household } from "@/lib/types";
import { type AddressSuggestion, geocodeAddress } from "@/lib/mapbox-geocode";
import { zodResolver } from "@/lib/zod-resolver";
import {
  type HouseholdFormInput,
  type HouseholdFormOutput,
  householdSchema,
} from "@/features/intake/householdSchema";

const DEFAULT_VALUES: HouseholdFormInput = {
  address: { street: "Am Nahholz", house_no: "54", city: "Buchen" },
  plz: "74722",
  floor_area_m2: "",
  building_year: "",
  occupants: "",
  electricity_eur_month: "",
  heating: { fuel: "OIL", eur_month: "" },
  mobility: { kind: "PETROL", km_month: "", eur_month: "" },
  existing_pv_kwp: "",
  existing_battery_kwh: "",
  existing_heatpump_year: "",
  existing_heatpump_power_kw: "",
  existing_heatpump_scop: "",
  existing_ev: false,
  existing_ev_charger: false,
};

const DEFAULT_HOUSE_COORDS = {
  lat: 49.53094,
  lon: 9.32659,
};

const inputBase =
  "w-full rounded-lg border bg-white px-3.5 py-2.5 text-[14px] text-text-1 outline-none transition-colors duration-150 ease-out-strong placeholder:text-text-3 focus:border-accent";

function inputClass(hasError: boolean) {
  return `${inputBase} ${hasError ? "border-danger focus:border-danger" : "border-border"}`;
}

function selectClass(hasError: boolean) {
  return `${inputClass(hasError)} cursor-pointer appearance-none pr-9`;
}

function ChevronDown() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-3"
    >
      <path
        d="M4 6l4 4 4-4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Field({
  label,
  htmlFor,
  error,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="mb-1.5 block text-[12px] font-medium text-text-2">
        {label}
      </label>
      {children}
      {error ? <p className="mt-1 text-[12px] font-medium text-danger">{error}</p> : null}
    </div>
  );
}

export interface IntakeFormProps {
  onComplete: (household: Household) => void;
  /** Called when an address suggestion is picked, with its coordinates. */
  onAddressPick?: (lat: number, lon: number) => void;
}

export default function IntakeForm({ onAddressPick, onComplete }: IntakeFormProps) {
  const [mobilityMode, setMobilityMode] = useState<"km" | "eur">("km");
  const [savedCity, setSavedCity] = useState<string | null>(null);

  // Address autocomplete state.
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [searching, setSearching] = useState(false);
  const justSelectedRef = useRef(false);

  const {
    register,
    watch,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<HouseholdFormInput, unknown, HouseholdFormOutput>({
    resolver: zodResolver<HouseholdFormInput, HouseholdFormOutput>(householdSchema),
    defaultValues: DEFAULT_VALUES,
    mode: "onBlur",
  });

  const carKind = watch("mobility.kind");
  const streetValue = watch("address.street");

  // Debounced geocode on street input. Skips the fetch triggered by our own
  // setValue after a selection (justSelectedRef).
  useEffect(() => {
    if (justSelectedRef.current) {
      justSelectedRef.current = false;
      return;
    }
    const query = streetValue?.trim() ?? "";
    if (query.length < 3) {
      setSuggestions([]);
      setSuggestOpen(false);
      setSearching(false);
      return;
    }

    const controller = new AbortController();
    setSearching(true);
    const timer = window.setTimeout(() => {
      geocodeAddress(query, controller.signal)
        .then((results) => {
          setSuggestions(results);
          setSuggestOpen(true);
          setActiveIndex(-1);
          setSearching(false);
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") {
            return; // superseded by a newer keystroke
          }
          setSuggestions([]);
          setSuggestOpen(false);
          setSearching(false);
        });
    }, 280);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [streetValue]);

  function selectSuggestion(suggestion: AddressSuggestion) {
    justSelectedRef.current = true;
    setValue("address.street", suggestion.street, { shouldValidate: true });
    if (suggestion.house_no) {
      setValue("address.house_no", suggestion.house_no, { shouldValidate: true });
    }
    if (suggestion.city) setValue("address.city", suggestion.city, { shouldValidate: true });
    if (suggestion.plz) setValue("plz", suggestion.plz, { shouldValidate: true });
    setSuggestions([]);
    setSuggestOpen(false);
    setActiveIndex(-1);
    onAddressPick?.(suggestion.lat, suggestion.lon);
  }

  function onStreetKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!suggestOpen || suggestions.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index - 1 + suggestions.length) % suggestions.length);
    } else if (event.key === "Enter") {
      // Don't submit the form while choosing an address.
      event.preventDefault();
      selectSuggestion(suggestions[activeIndex >= 0 ? activeIndex : 0]);
    } else if (event.key === "Escape") {
      setSuggestOpen(false);
    }
  }

  function switchMobilityMode(mode: "km" | "eur") {
    if (mode === mobilityMode) return;
    setValue(mode === "km" ? "mobility.eur_month" : "mobility.km_month", "");
    setMobilityMode(mode);
  }

  const showHouse = async () => {
    const data = getValues();
    const fullAddress = `${data.address.street} ${data.address.house_no}, ${data.plz} ${data.address.city}`;
    const [match] = await geocodeAddress(fullAddress);
    if (match) {
      onAddressPick?.(match.lat, match.lon);
    } else if (
      data.address.street.trim().toLowerCase() === "am nahholz" &&
      data.address.house_no.trim() === "54" &&
      data.plz.trim() === "74722"
    ) {
      onAddressPick?.(DEFAULT_HOUSE_COORDS.lat, DEFAULT_HOUSE_COORDS.lon);
    }
    setSavedCity(data.address.city);

    // Emit the parsed Household so downstream steps (3D model, /recommend) have
    // it. Parse failures just skip — the user can still preview the house.
    const parsed = householdSchema.safeParse(data);
    if (parsed.success) onComplete(parsed.data as Household);
  };

  const streetRegister = register("address.street");
  const mobilityError = errors.mobility?.km_month?.message ?? errors.mobility?.eur_month?.message;

  return (
    <form
      onSubmit={(event) => event.preventDefault()}
      noValidate
      className="box-border flex h-full min-h-0 w-full flex-col pt-[52px] font-sans"
    >
      <div className="shrink-0 border-b border-border px-7 pb-5 pt-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-3">
          Heimwende · Your details
        </p>
        <h1 className="mt-1.5 text-[22px] font-bold leading-tight tracking-[-0.01em] text-text-1">
          What does energy cost you today?
        </h1>
        <p className="mt-1.5 text-[13px] leading-relaxed text-text-2">
          One-time entry. No account, no upload, no home visit.
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="grid gap-4 px-7 py-6">
          {/* Address — street field is the Mapbox autocomplete */}
          <div className="grid grid-cols-[1fr_88px] gap-3">
            <Field label="Street" htmlFor="street" error={errors.address?.street?.message}>
              <div className="relative">
                <input
                  id="street"
                  autoComplete="off"
                  placeholder="Search address..."
                  className={inputClass(Boolean(errors.address?.street))}
                  {...streetRegister}
                  onKeyDown={onStreetKeyDown}
                  onFocus={() => {
                    if (suggestions.length > 0) setSuggestOpen(true);
                  }}
                  onBlur={(event) => {
                    streetRegister.onBlur(event);
                    // Delay so a suggestion click registers before we close.
                    window.setTimeout(() => setSuggestOpen(false), 120);
                  }}
                />
                {searching ? (
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-text-3">
                    …
                  </span>
                ) : null}
                {suggestOpen && suggestions.length > 0 ? (
                  <ul className="address-suggest absolute left-0 right-0 top-[calc(100%+6px)] z-20 overflow-hidden rounded-lg border border-border bg-white py-1 shadow-[var(--shadow-md)]">
                    {suggestions.map((suggestion, index) => (
                      <li key={suggestion.id}>
                        <button
                          type="button"
                          onMouseDown={(event) => event.preventDefault()}
                          onMouseEnter={() => setActiveIndex(index)}
                          onClick={() => selectSuggestion(suggestion)}
                          className={`block w-full px-3.5 py-2 text-left transition-colors duration-150 ${
                            index === activeIndex ? "bg-accent-soft" : "bg-white hover:bg-surface"
                          }`}
                        >
                          <span className="block text-[13px] font-medium text-text-1">
                            {suggestion.street}
                            {suggestion.house_no ? ` ${suggestion.house_no}` : ""}
                          </span>
                          <span className="block text-[12px] text-text-3">
                            {[suggestion.plz, suggestion.city].filter(Boolean).join(" ")}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </Field>
            <Field label="House no." htmlFor="house_no" error={errors.address?.house_no?.message}>
              <input
                id="house_no"
                placeholder="54"
                className={inputClass(Boolean(errors.address?.house_no))}
                {...register("address.house_no")}
              />
            </Field>
          </div>

        <div className="grid grid-cols-[120px_1fr] gap-3">
          <Field label="Postal code" htmlFor="plz" error={errors.plz?.message}>
            <input
              id="plz"
              inputMode="numeric"
              autoComplete="off"
              placeholder="74722"
              className={inputClass(Boolean(errors.plz))}
              {...register("plz")}
            />
          </Field>
          <Field label="City" htmlFor="city" error={errors.address?.city?.message}>
            <input
              id="city"
              autoComplete="off"
              placeholder="Buchen"
              className={inputClass(Boolean(errors.address?.city))}
              {...register("address.city")}
            />
          </Field>
        </div>

        {/* Building */}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Living area m²" htmlFor="floor_area" error={errors.floor_area_m2?.message}>
            <input
              id="floor_area"
              type="number"
              inputMode="numeric"
              placeholder="165"
              className={inputClass(Boolean(errors.floor_area_m2))}
              {...register("floor_area_m2")}
            />
          </Field>
          <Field label="Build year" htmlFor="building_year" error={errors.building_year?.message}>
            <input
              id="building_year"
              type="number"
              inputMode="numeric"
              placeholder="1985"
              className={inputClass(Boolean(errors.building_year))}
              {...register("building_year")}
            />
          </Field>
          <Field label="People" htmlFor="occupants" error={errors.occupants?.message}>
            <input
              id="occupants"
              type="number"
              inputMode="numeric"
              placeholder="4"
              className={inputClass(Boolean(errors.occupants))}
              {...register("occupants")}
            />
          </Field>
        </div>

        {/* Electricity */}
        <Field
          label="Electricity cost (EUR/month)"
          htmlFor="electricity"
          error={errors.electricity_eur_month?.message}
        >
          <input
            id="electricity"
            type="number"
            inputMode="numeric"
            placeholder="130"
            className={inputClass(Boolean(errors.electricity_eur_month))}
            {...register("electricity_eur_month")}
          />
        </Field>

        {/* Heating */}
        <div className="grid grid-cols-[140px_1fr] gap-3">
          <Field label="Heating" htmlFor="fuel" error={errors.heating?.fuel?.message}>
            <div className="relative">
              <select
                id="fuel"
                className={selectClass(Boolean(errors.heating?.fuel))}
                {...register("heating.fuel")}
              >
                <option value="GAS">Gas</option>
                <option value="OIL">Oil</option>
              </select>
              <ChevronDown />
            </div>
          </Field>
          <Field
            label="Heating cost (EUR/month)"
            htmlFor="heating_eur"
            error={errors.heating?.eur_month?.message}
          >
            <input
              id="heating_eur"
              type="number"
              inputMode="numeric"
              placeholder="160"
              className={inputClass(Boolean(errors.heating?.eur_month))}
              {...register("heating.eur_month")}
            />
          </Field>
        </div>

        {/* Mobility */}
        <div className="grid grid-cols-[140px_1fr] gap-3">
          <Field label="Mobility" htmlFor="car_kind" error={errors.mobility?.kind?.message}>
            <div className="relative">
              <select
                id="car_kind"
                className={selectClass(Boolean(errors.mobility?.kind))}
                {...register("mobility.kind")}
              >
                <option value="PETROL">Petrol</option>
                <option value="DIESEL">Diesel</option>
                <option value="EV">EV</option>
                <option value="NONE">No car</option>
              </select>
              <ChevronDown />
            </div>
          </Field>

          {carKind !== "NONE" ? (
            <Field
              label={mobilityMode === "km" ? "Mileage" : "Fuel cost"}
              error={mobilityError}
            >
              <div className="flex gap-2">
                {mobilityMode === "km" ? (
                  <input
                    key="km"
                    type="number"
                    inputMode="numeric"
                    placeholder="1200"
                    aria-label="Kilometers per month"
                    className={inputClass(Boolean(mobilityError))}
                    {...register("mobility.km_month")}
                  />
                ) : (
                  <input
                    key="eur"
                    type="number"
                    inputMode="numeric"
                    placeholder="180"
                    aria-label="Euro per month"
                    className={inputClass(Boolean(mobilityError))}
                    {...register("mobility.eur_month")}
                  />
                )}
                <div className="flex shrink-0 overflow-hidden rounded-lg border border-border">
                  <ToggleButton
                    active={mobilityMode === "km"}
                    onClick={() => switchMobilityMode("km")}
                  >
                    km
                  </ToggleButton>
                  <ToggleButton
                    active={mobilityMode === "eur"}
                    onClick={() => switchMobilityMode("eur")}
                  >
                    €
                  </ToggleButton>
                </div>
              </div>
            </Field>
          ) : (
            <div className="hidden sm:block" />
          )}
        </div>
        </div>

        {/* Existing equipment — collapsible optional section */}
        <ExistingEquipment register={register} errors={errors} />
      </div>

      <div className="shrink-0 border-t border-border px-7 py-5">
        <div className="flex items-center justify-between gap-4">
        {savedCity ? (
          <p className="text-[12px] font-medium text-success">Details saved · {savedCity} ✓</p>
        ) : (
          <p className="text-[12px] text-text-3">All fields are required.</p>
        )}
        <button
          type="button"
          onClick={showHouse}
          disabled={isSubmitting}
          className="inline-flex h-11 shrink-0 items-center justify-center rounded-xl bg-accent px-5 text-[13px] font-semibold text-white shadow-sm transition-[transform,filter] duration-150 ease-out-strong hover:brightness-95 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-60"
        >
          Show house
        </button>
        </div>
      </div>
    </form>
  );
}

function ExistingEquipment({
  register,
  errors,
}: {
  register: UseFormRegister<HouseholdFormInput>;
  errors: FieldErrors<HouseholdFormInput>;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <div className="border-t border-border">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between px-7 py-4 text-left transition-colors duration-150 ease-out-strong hover:bg-surface"
      >
        <span className="text-[13px] font-medium text-text-2">
          Existing equipment{" "}
          <span className="text-text-3 font-normal">(optional)</span>
        </span>
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          className={`h-3.5 w-3.5 shrink-0 text-text-3 transition-transform duration-200 ease-out-strong ${open ? "rotate-180" : ""}`}
        >
          <path
            d="M4 6l4 4 4-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      <div
        id={panelId}
        className="overflow-hidden transition-[max-height,opacity] duration-300 ease-out-strong motion-reduce:transition-none"
        style={{ maxHeight: open ? "600px" : "0px", opacity: open ? 1 : 0 }}
      >
        <div className="grid gap-4 px-7 pb-6 pt-1">
          {/* Solar + battery */}
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="PV system (kWp)"
              htmlFor="existing_pv_kwp"
              error={errors.existing_pv_kwp?.message}
            >
              <input
                id="existing_pv_kwp"
                type="number"
                inputMode="decimal"
                placeholder="6.5"
                className={inputClass(Boolean(errors.existing_pv_kwp))}
                {...register("existing_pv_kwp")}
              />
            </Field>
            <Field
              label="Battery (kWh)"
              htmlFor="existing_battery_kwh"
              error={errors.existing_battery_kwh?.message}
            >
              <input
                id="existing_battery_kwh"
                type="number"
                inputMode="decimal"
                placeholder="10"
                className={inputClass(Boolean(errors.existing_battery_kwh))}
                {...register("existing_battery_kwh")}
              />
            </Field>
          </div>

          {/* Heat pump */}
          <div className="grid grid-cols-3 gap-3">
            <Field
              label="Heat pump year"
              htmlFor="existing_heatpump_year"
              error={errors.existing_heatpump_year?.message}
            >
              <input
                id="existing_heatpump_year"
                type="number"
                inputMode="numeric"
                placeholder="2018"
                className={inputClass(Boolean(errors.existing_heatpump_year))}
                {...register("existing_heatpump_year")}
              />
            </Field>
            <Field
              label="Heat pump output (kW)"
              htmlFor="existing_heatpump_power_kw"
              error={errors.existing_heatpump_power_kw?.message}
            >
              <input
                id="existing_heatpump_power_kw"
                type="number"
                inputMode="decimal"
                placeholder="8"
                className={inputClass(Boolean(errors.existing_heatpump_power_kw))}
                {...register("existing_heatpump_power_kw")}
              />
            </Field>
            <Field
              label="SCOP"
              htmlFor="existing_heatpump_scop"
              error={errors.existing_heatpump_scop?.message}
            >
              <input
                id="existing_heatpump_scop"
                type="number"
                inputMode="decimal"
                placeholder="3.5"
                className={inputClass(Boolean(errors.existing_heatpump_scop))}
                {...register("existing_heatpump_scop")}
              />
            </Field>
          </div>

          {/* EV checkboxes */}
          <div className="flex flex-col gap-2.5">
            <CheckboxField id="existing_ev" label="EV already owned" register={register} />
            <CheckboxField
              id="existing_ev_charger"
              label="Wallbox already installed"
              register={register}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function CheckboxField({
  id,
  label,
  register,
}: {
  id: "existing_ev" | "existing_ev_charger";
  label: string;
  register: UseFormRegister<HouseholdFormInput>;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 text-[13px] text-text-2">
      <input
        id={id}
        type="checkbox"
        className="h-4 w-4 cursor-pointer accent-accent"
        {...register(id)}
      />
      {label}
    </label>
  );
}

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`px-3 text-[13px] font-semibold transition-colors duration-150 ease-out-strong ${
        active ? "bg-accent-soft text-accent" : "bg-white text-text-2 hover:bg-surface"
      }`}
    >
      {children}
    </button>
  );
}

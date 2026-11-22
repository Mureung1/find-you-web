import { ChevronDown, MapPin, type LucideIcon } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";
import { categories, type Location } from "@/lib/find-you";

type SelectProps = ComponentPropsWithoutRef<"select"> & { icon?: LucideIcon };

export function SelectField({ icon: Icon, children, ...props }: SelectProps) {
  return (
    <span className={`select-field${Icon ? " select-with-icon" : ""}`}>
      {Icon && <Icon className="select-icon" size={17} aria-hidden />}
      <select {...props}>{children}</select>
      <ChevronDown className="select-chevron" size={16} aria-hidden />
    </span>
  );
}

export function CategorySelect({ placeholder, ...props }: SelectProps & { placeholder: string }) {
  return (
    <SelectField {...props}>
      <option value="">{placeholder}</option>
      {Object.entries(categories).map(([key, category]) => <option key={key} value={key}>{category.label}</option>)}
    </SelectField>
  );
}

export const regionPrefix = "region:";

export function NeighborhoodSelect({
  locations, placeholder, includeRegions = false, ...props
}: SelectProps & { locations: Location[]; placeholder: string; includeRegions?: boolean }) {
  const groups = new Map<string, Location[]>();
  for (const location of locations) {
    const group = groups.get(location.region) ?? [];
    group.push(location);
    groups.set(location.region, group);
  }

  return (
    <SelectField icon={MapPin} {...props}>
      <option value="">{placeholder}</option>
      {Array.from(groups, ([region, neighborhoods]) => (
        <optgroup key={region} label={region}>
          {includeRegions && <option value={`${regionPrefix}${region}`}>{region} 전체</option>}
          {neighborhoods.map((location) => (
            <option key={location.location_id} value={location.location_id}>{location.dong}</option>
          ))}
        </optgroup>
      ))}
    </SelectField>
  );
}

import { ChevronDown, type LucideIcon } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";
import { categories } from "@/lib/find-you";

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

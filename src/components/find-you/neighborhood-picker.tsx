"use client";

import { MapPin } from "lucide-react";
import { type KeyboardEvent, useEffect, useMemo, useState } from "react";
import type { Location } from "@/lib/find-you";
import styles from "./neighborhood-picker.module.css";

export const regionPrefix = "region:";
const optionLimit = 12;

type Option = { value: string; label: string; keywords: string; compact: string };

type Props = {
  id: string;
  name?: string;
  locations: Location[];
  value: string;
  onChange: (value: string) => void;
  onEdit?: () => void;
  placeholder: string;
  includeRegions?: boolean;
  required?: boolean;
  disabled?: boolean;
};

function option(value: string, label: string): Option {
  const keywords = label.normalize("NFKC");
  return { value, label, keywords, compact: keywords.replace(/\s+/g, "") };
}

export function NeighborhoodPicker({
  id, name, locations, value, onChange, onEdit, placeholder, includeRegions, required, disabled,
}: Props) {
  const [query, setQuery] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = id + "-options";

  const options = useMemo(() => {
    const towns = locations.map(({ location_id, region, dong }) =>
      option(location_id, region + " " + dong));
    if (!includeRegions) return towns;
    const regions = [...new Set(locations.map(({ region }) => region))];
    return [option("", "전체 동네"), ...regions.map((region) => option(regionPrefix + region, region + " 전체")), ...towns];
  }, [locations, includeRegions]);

  const committed = options.find((choice) => choice.value === value);
  const terms = (query ?? "").normalize("NFKC").replaceAll("서울특별시", "서울").trim().split(/\s+/).filter(Boolean);
  const compact = terms.join("");
  const matches = terms.length
    ? options.filter((choice) => choice.compact.includes(compact) || terms.every((term) => choice.keywords.includes(term)))
    : options.filter((choice) => choice.value === value || choice.value === "");
  const visible = matches.slice(0, optionLimit);
  const activeOption = open && active >= 0 && active < visible.length ? listId + "-" + active : undefined;

  useEffect(() => {
    if (activeOption) document.getElementById(activeOption)?.scrollIntoView({ block: "nearest" });
  }, [activeOption]);

  function close() {
    setOpen(false);
    setQuery(null);
    setActive(-1);
  }

  function choose(choice: Option) {
    onChange(choice.value);
    close();
  }

  function keyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!visible.length) return;
      event.preventDefault();
      setOpen(true);
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setActive((index) => index < 0 ? (direction > 0 ? 0 : visible.length - 1)
        : (index + direction + visible.length) % visible.length);
    } else if (event.key === "Enter" && open && (active >= 0 || terms.length > 0)) {
      event.preventDefault();
      const choice = visible[active >= 0 ? active : 0];
      if (choice) choose(choice);
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      close();
    }
  }

  return (
    <div className={styles.picker}>
      <div className={styles.inputWrap}>
        <MapPin size={17} aria-hidden />
        <input id={id} role="combobox" type="text" value={query ?? (value ? committed?.label ?? "" : "")}
          placeholder={placeholder} maxLength={100} autoComplete="off" required={required} disabled={disabled}
          aria-autocomplete="list" aria-expanded={open && visible.length > 0}
          aria-controls={open && visible.length ? listId : undefined} aria-activedescendant={activeOption}
          onFocus={(event) => { event.currentTarget.select(); setOpen(true); }}
          onClick={() => setOpen(true)} onBlur={close} onKeyDown={keyDown}
          onChange={(event) => {
            onEdit?.();
            if (required && value) onChange("");
            setQuery(event.target.value);
            setActive(-1);
            setOpen(true);
          }} />
        {name && <input type="hidden" name={name} value={value} />}
      </div>
      {open && (
        <div className={styles.dropdown}>
          {visible.length ? (
            <ul id={listId} className={styles.options} role="listbox" aria-label="동네 검색 결과">
              {visible.map((choice, index) => (
                <li key={choice.value} role="presentation">
                  <button id={listId + "-" + index} type="button" tabIndex={-1} role="option"
                    aria-selected={choice.value === value} data-active={index === active}
                    onMouseDown={(event) => event.preventDefault()} onClick={() => choose(choice)}>
                    {choice.label}
                  </button>
                </li>
              ))}
            </ul>
          ) : <p role="status">{terms.length ? "일치하는 동네가 없어요." : "시·군·구나 읍·면·동 이름을 입력해 주세요."}</p>}
          {matches.length > optionLimit && <p>동네 이름을 더 입력하면 결과를 좁힐 수 있어요.</p>}
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import type { SearchableOption } from "@/components/SearchableSelect";

type Props = {
  id?: string;
  label: string;
  options: readonly SearchableOption[];
  values: readonly string[];
  onChange: (values: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
  emptyMessage?: string;
  maxVisible?: number;
  /** Optional cap (e.g. keep school lists reasonable). */
  maxSelections?: number;
};

export function SearchableMultiSelect({
  id: idProp,
  label,
  options,
  values,
  onChange,
  disabled = false,
  placeholder = "Search to add…",
  emptyMessage = "No matches",
  maxVisible = 120,
  maxSelections,
}: Props) {
  const autoId = useId();
  const listId = `${autoId}-listbox`;
  const inputId = idProp ?? `${autoId}-input`;
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const valueSet = useMemo(() => new Set(values), [values]);
  const atCap = maxSelections !== undefined && values.length >= maxSelections;

  const availableOptions = useMemo(
    () => options.filter((o) => !valueSet.has(o.value)),
    [options, valueSet],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return availableOptions.slice(0, maxVisible);
    const hits = availableOptions.filter(
      (o) =>
        o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q),
    );
    return hits.slice(0, maxVisible);
  }, [availableOptions, query, maxVisible]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const add = (v: string) => {
    if (valueSet.has(v)) return;
    if (maxSelections !== undefined && values.length >= maxSelections) return;
    onChange([...values, v]);
    setQuery("");
    setOpen(false);
  };

  const remove = (v: string) => {
    onChange(values.filter((x) => x !== v));
  };

  const selectedLabels = useMemo(() => {
    const map = new Map(options.map((o) => [o.value, o.label] as const));
    return values.map((v) => ({ value: v, label: map.get(v) ?? v }));
  }, [options, values]);

  return (
    <div ref={rootRef} className="relative">
      <span className="block text-xs font-medium text-neutral-700">{label}</span>
      {selectedLabels.length > 0 ? (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {selectedLabels.map(({ value: v, label: lb }) => (
            <li key={v}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => remove(v)}
                className="inline-flex max-w-full items-center gap-1 rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-left text-xs text-neutral-800 transition-colors hover:border-neutral-300 hover:bg-neutral-100 disabled:opacity-50"
                title="Remove"
              >
                <span className="truncate">{lb}</span>
                <span className="shrink-0 text-neutral-400" aria-hidden>
                  ×
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        disabled={disabled || atCap}
        value={open ? query : ""}
        placeholder={atCap ? `Maximum ${maxSelections} selected` : placeholder}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!open) setOpen(true);
        }}
        onFocus={() => {
          if (atCap) return;
          setOpen(true);
        }}
        className="mt-2 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25 disabled:opacity-50"
      />
      {open && !disabled && !atCap && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-[55] mt-1 max-h-56 w-full overflow-auto rounded-xl border border-neutral-200/90 bg-white py-1 text-sm shadow-lg ring-1 ring-black/5"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-neutral-500">{emptyMessage}</li>
          ) : (
            filtered.map((opt) => (
              <li key={opt.value} role="presentation">
                <button
                  type="button"
                  role="option"
                  className="w-full px-3 py-2 text-left hover:bg-neutral-100 focus:bg-neutral-100 focus:outline-none"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => add(opt.value)}
                >
                  {opt.label}
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}

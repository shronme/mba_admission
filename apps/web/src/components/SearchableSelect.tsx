"use client";

import { useCallback, useId, useMemo, useRef, useState } from "react";

export type SearchableOption = { value: string; label: string };

type Props = {
  id?: string;
  label: string;
  options: readonly SearchableOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  emptyMessage?: string;
  /** Max options to render while filtering (keeps DOM light). */
  maxVisible?: number;
};

export function SearchableSelect({
  id: idProp,
  label,
  options,
  value,
  onChange,
  disabled = false,
  placeholder = "Type to search…",
  emptyMessage = "No matches",
  maxVisible = 120,
}: Props) {
  const autoId = useId();
  const listId = `${autoId}-listbox`;
  const inputId = idProp ?? `${autoId}-input`;
  const rootRef = useRef<HTMLDivElement>(null);
  const queryRef = useRef("");
  const optionsRef = useRef(options);
  const onChangeRef = useRef(onChange);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  queryRef.current = query;
  optionsRef.current = options;
  onChangeRef.current = onChange;

  /** Apply typed text to `value` when it exactly matches an option; empty input clears. */
  const commitQuery = useCallback(() => {
    const raw = queryRef.current.trim();
    const q = raw.toLowerCase();
    if (!q) {
      onChangeRef.current("");
      return;
    }
    const exact = optionsRef.current.find(
      (o) => o.label.toLowerCase() === q || o.value.toLowerCase() === q,
    );
    if (exact) onChangeRef.current(exact.value);
  }, []);

  const selected = useMemo(
    () => options.find((o) => o.value === value) ?? null,
    [options, value],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options.slice(0, maxVisible);
    const hits = options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q),
    );
    return hits.slice(0, maxVisible);
  }, [options, query, maxVisible]);

  const displayValue = open ? query : selected?.label ?? "";

  return (
    <div ref={rootRef} className="relative">
      <label htmlFor={inputId} className="block text-xs font-medium text-neutral-700">
        {label}
      </label>
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        disabled={disabled}
        value={displayValue}
        placeholder={placeholder}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!open) setOpen(true);
        }}
        onBlur={() => {
          window.setTimeout(() => {
            if (rootRef.current?.contains(document.activeElement)) return;
            commitQuery();
            setOpen(false);
          }, 0);
        }}
        onFocus={() => {
          setOpen(true);
          setQuery(selected?.label ?? "");
        }}
        className="mt-1 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25 disabled:opacity-50"
      />
      {open && !disabled && (
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
                  aria-selected={opt.value === value}
                  className="w-full px-3 py-2 text-left hover:bg-neutral-100 focus:bg-neutral-100 focus:outline-none"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onChange(opt.value);
                    setQuery(opt.label);
                    setOpen(false);
                  }}
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

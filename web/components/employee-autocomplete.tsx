"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { searchEmployees, type EmployeeOption } from "@/app/actions";

export function EmployeeAutocomplete({
  onChange,
  placeholder = "Buscar funcionário...",
  required,
}: {
  onChange: (id: string, name: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<EmployeeOption[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const listId = "employee-autocomplete-listbox";

  function handleChange(v: string) {
    setQuery(v);
    onChange("", "");
    setActiveIndex(-1);
    clearTimeout(timer.current);
    if (v.trim().length < 1) {
      setOptions([]);
      setOpen(false);
      return;
    }
    timer.current = setTimeout(() => {
      searchEmployees(v).then((r) => {
        setOptions(r);
        setOpen(r.length > 0);
        setActiveIndex(-1);
      });
    }, 250);
  }

  function select(emp: EmployeeOption) {
    setQuery(emp.name);
    onChange(String(emp.id), emp.name);
    setOpen(false);
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (!open || !options.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      select(options[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="autocomplete-wrap" role="combobox" aria-expanded={open} aria-haspopup="listbox" aria-owns={listId}>
      <input
        className="employee-search-input"
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => {
          if (options.length) setOpen(true);
        }}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        aria-autocomplete="list"
        aria-controls={listId}
        aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
      />
      {open && (
        <ul id={listId} className="autocomplete-list" role="listbox">
          {options.map((emp, i) => (
            <li
              key={emp.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              className={i === activeIndex ? "active" : undefined}
              onMouseDown={() => select(emp)}
            >
              <strong>{emp.name}</strong>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

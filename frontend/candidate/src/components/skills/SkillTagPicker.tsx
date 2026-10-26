import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { normalizeSkill, skillOptions, uniqueSkills } from "./skillCatalog";
import type { SkillOption } from "./skillCatalog";
import "./SkillTagPicker.css";

export type SkillTagPickerProps = {
  value: readonly string[];
  onChange: (value: string[]) => void;
  options?: readonly SkillOption[];
  label?: string;
  disabled?: boolean;
};

export function SkillTagPicker({ value, onChange, options = [], label = "技能（选填）", disabled = false }: SkillTagPickerProps) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [announcement, setAnnouncement] = useState("");
  const selected = uniqueSkills(value);
  const catalog = skillOptions(options);
  const term = normalizeSkill(query);
  const exact = catalog.find(option => option.value === term || normalizeSkill(option.label) === term);
  const alreadySelected = selected.includes(exact?.value ?? term);
  const matches = catalog.filter(option => !selected.includes(option.value) && (
    option.value.includes(term) || normalizeSkill(option.label).includes(term)
  )).sort((a, b) => Number(b.value.startsWith(term)) - Number(a.value.startsWith(term)) || a.label.localeCompare(b.label))
    .slice(0, 8);
  const custom = term && !exact && !alreadySelected ? { value: term, label: query.trim() } : null;
  const suggestions = [...matches, ...(custom ? [custom] : [])];
  const expanded = open && !disabled;
  const activeIndex = active >= 0 && active < suggestions.length ? active : -1;

  useEffect(() => {
    if (expanded && activeIndex >= 0) {
      document.getElementById(`${id}-option-${activeIndex}`)?.scrollIntoView({ block: "nearest" });
    }
  }, [expanded, activeIndex, id]);

  function updateQuery(next: string) {
    setQuery(next);
    setActive(-1);
    input.current?.setCustomValidity(next.trim() ? "请先选择推荐技能、创建自定义标签，或清空搜索框。" : "");
  }

  function choose(option: SkillOption) {
    if (disabled) return;
    onChange(uniqueSkills([...selected, option.value]));
    setAnnouncement(`已添加 ${option.label}`);
    updateQuery("");
    setOpen(true);
    input.current?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.nativeEvent.isComposing || disabled) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (suggestions.length) {
        setActive(event.key === "ArrowDown"
          ? (activeIndex + 1) % suggestions.length
          : (activeIndex <= 0 ? suggestions.length : activeIndex) - 1);
      }
    } else if (event.key === "Enter" && (expanded || term)) {
      event.preventDefault();
      if (alreadySelected && activeIndex < 0) {
        setAnnouncement("该技能已添加，请勿重复选择。");
        updateQuery("");
        return;
      }
      const choice = suggestions[activeIndex >= 0 ? activeIndex : 0];
      if (choice) choose(choice);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      setActive(-1);
    }
  }

  return (
    <div className="skill-picker" onBlur={event => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
    }}>
      <label htmlFor={`${id}-input`}>{label}</label>
      <p id={`${id}-help`} className="skill-picker-help">搜索并选择技能；没有合适的选项时，可创建自定义标签。</p>
      {selected.length > 0 && <ul className="skill-picker-tags" aria-label="已选技能">
        {selected.map(skill => {
          const display = catalog.find(option => option.value === skill)?.label ?? skill;
          return <li key={skill}>
            <span>{display}</span>
            <button type="button" disabled={disabled} aria-label={`移除技能 ${display}`} onClick={() => {
              onChange(selected.filter(item => item !== skill));
              setAnnouncement(`已移除 ${display}`);
            }}>×</button>
          </li>;
        })}
      </ul>}
      <div className="skill-picker-search">
        <input id={`${id}-input`} ref={input} role="combobox" type="text" autoComplete="off"
          value={query} disabled={disabled} placeholder="搜索技能，例如 Java"
          aria-autocomplete="list" aria-expanded={expanded} aria-controls={expanded ? `${id}-options` : undefined}
          aria-activedescendant={expanded && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
          aria-describedby={`${id}-help ${id}-notice`}
          onFocus={() => setOpen(true)} onKeyDown={handleKeyDown}
          onChange={event => { updateQuery(event.target.value); setOpen(true); }} />
        {expanded && <div className="skill-picker-dropdown">
          <ul id={`${id}-options`} role="listbox" aria-label="技能建议">
            {suggestions.map((option, index) => <li key={option.value} role="option"
              id={`${id}-option-${index}`} aria-selected={index === activeIndex}
              onMouseDown={event => event.preventDefault()} onMouseMove={() => setActive(index)}
              onClick={() => choose(option)}>
              <span>{option === custom ? `自定义：${option.label}` : option.label}</span>
              <small>{option === custom ? "创建标签" : "添加"}</small>
            </li>)}
          </ul>
          {!suggestions.length && <p>{alreadySelected ? "该技能已添加。" : "没有可添加的技能。"}</p>}
        </div>}
      </div>
      <p id={`${id}-notice`} className="skill-picker-notice" role="status" aria-live="polite">
        {announcement || (selected.length ? `已选择 ${selected.length} 项技能` : "尚未选择技能，可以稍后补充。")}
      </p>
    </div>
  );
}

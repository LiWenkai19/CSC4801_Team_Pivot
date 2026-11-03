import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { normalizeSkill, skillOptions, uniqueSkills } from "./skillCatalog";
import type { SkillOption } from "./skillCatalog";
import "./SkillTagPicker.css";

// 父组件拥有已选技能；本组件通过 value 接收、通过 onChange 通知父组件更新。
export type SkillTagPickerProps = {
  value: readonly string[];
  onChange: (value: string[]) => void;
  options?: readonly SkillOption[];
  label?: string;
  disabled?: boolean;
};

export function SkillTagPicker({ value, onChange, options = [], label = "技能（选填）", disabled = false }: SkillTagPickerProps) {
  // useId 生成关联标签和下拉列表的 ID；ref 用来操作真实输入框。
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  // query 是搜索文字；open 控制下拉；active 是键盘选中的下标，-1 表示未选择。
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [announcement, setAnnouncement] = useState("");
  // 先规范化已选值和搜索词，再合并预设目录与调用方传入的选项。
  const selected = uniqueSkills(value);
  const catalog = skillOptions(options);
  const term = normalizeSkill(query);
  const exact = catalog.find(option => option.value === term || normalizeSkill(option.label) === term);
  const alreadySelected = selected.includes(exact?.value ?? term);
  // 排除已选项；同时搜索保存值和展示名；前缀匹配优先，最多显示八条推荐。
  const matches = catalog.filter(option => !selected.includes(option.value) && (
    option.value.includes(term) || normalizeSkill(option.label).includes(term)
  )).sort((a, b) => Number(b.value.startsWith(term)) - Number(a.value.startsWith(term)) || a.label.localeCompare(b.label))
    .slice(0, 8);
  // 不存在完全匹配且尚未选中过时，提供自定义选项，保留用户输入的展示大小写。
  const custom = term && !exact && !alreadySelected ? { value: term, label: query.trim() } : null;
  const suggestions = [...matches, ...(custom ? [custom] : [])];
  const expanded = open && !disabled;
  const activeIndex = active >= 0 && active < suggestions.length ? active : -1;

  useEffect(() => {
    // 键盘选项变化时将其滚动到可见范围，不改变选中技能。
    if (expanded && activeIndex >= 0) {
      document.getElementById(`${id}-option-${activeIndex}`)?.scrollIntoView({ block: "nearest" });
    }
  }, [expanded, activeIndex, id]);

  function updateQuery(next: string) {
    // 搜索文字尚未确认为标签时阻止表单提交，防止用户以为输入已保存。
    setQuery(next);
    setActive(-1);
    input.current?.setCustomValidity(next.trim() ? "请先选择推荐技能、创建自定义标签，或清空搜索框。" : "");
  }

  function choose(option: SkillOption) {
    // 选择后去重并通知父组件，同时清空搜索、播报结果并把焦点留在输入框。
    if (disabled) return;
    onChange(uniqueSkills([...selected, option.value]));
    setAnnouncement(`已添加 ${option.label}`);
    updateQuery("");
    setOpen(true);
    input.current?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    // 输入法正在组合字符时不处理 Enter，避免中文拼音确认被误当成选择技能。
    if (event.nativeEvent.isComposing || disabled) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      // 上下键在候选项中循环；preventDefault 阻止浏览器执行默认滚动。
      event.preventDefault();
      setOpen(true);
      if (suggestions.length) {
        setActive(event.key === "ArrowDown"
          ? (activeIndex + 1) % suggestions.length
          : (activeIndex <= 0 ? suggestions.length : activeIndex) - 1);
      }
    } else if (event.key === "Enter" && (expanded || term)) {
      // Enter 选择高亮项（没有高亮时选第一项）；重复技能只提示，不重复添加。
      event.preventDefault();
      if (alreadySelected && activeIndex < 0) {
        setAnnouncement("该技能已添加，请勿重复选择。");
        updateQuery("");
        return;
      }
      const choice = suggestions[activeIndex >= 0 ? activeIndex : 0];
      if (choice) choose(choice);
    } else if (event.key === "Escape") {
      // Escape 仅关闭建议列表，不删除已经选择的标签。
      event.preventDefault();
      setOpen(false);
      setActive(-1);
    }
  }

  // JSX 描述界面：已选标签可以移除，下拉项支持鼠标和键盘，状态文字供读屏器播报。
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

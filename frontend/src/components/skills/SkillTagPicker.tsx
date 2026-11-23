import { useEffect, useId, useRef, useState } from 'react'
import './SkillTagPicker.css'
import { useLanguage } from '../../i18n/LanguageContext'
import type { Message } from '../../i18n/LanguageContext'
import { displaySkillName, filterSuggestions, normalizeSkillText } from './skillCatalog'

type Props = {
    value: string[]
    onChange: (skills: string[]) => void
    /** 分组标题；由使用方按角色语境提供，不设默认值。 */
    legend: string
    /** 已选技能列表的无障碍名称。 */
    selectedLabel: string
    /** 输入框上方的标签。 */
    inputLabel: string
    /** 添加按钮文字。 */
    addLabel: string
    /** 输入框下方的帮助文字。 */
    help: string
    /** 搜索无匹配时的提示。 */
    emptyHint: string
}

/** 搜索预设技能、维护已选标签；文案由角色封装提供，缺失时构建期报错。 */
function SkillTagPicker({
    value,
    onChange,
    legend,
    selectedLabel,
    inputLabel,
    addLabel,
    help,
    emptyHint,
}: Props) {
    const { t } = useLanguage()
    const id = useId()
    const input = useRef<HTMLInputElement>(null)
    const [query, setQuery] = useState('')
    const [notice, setNotice] = useState<Message | ''>('')
    const validationMessage = t('skills.uncommitted')
    const options = filterSuggestions(query, value)

    // 语言切换后重新套用原生校验文案，避免残留旧语言。
    useEffect(() => {
        const field = input.current
        field?.setCustomValidity(field.value.trim() ? validationMessage : '')
    }, [validationMessage])

    /** matched 表示从搜索建议中点选；自由输入（Enter 或按钮）按自定义技能处理。 */
    function add(text: string, matched = false) {
        const name = normalizeSkillText(text)
        if (!name) return
        const alreadyChosen = value.includes(name)
        if (!alreadyChosen) onChange([...value, name])
        const skill = displaySkillName(name)
        setNotice(
            alreadyChosen
                ? { key: 'skills.alreadySelected', values: { skill } }
                : matched
                    ? { key: 'skills.matched', values: { skill } }
                    : { key: 'skills.added', values: { skill } },
        )
        setQuery('')
        input.current?.setCustomValidity('')
        input.current?.focus()
    }

    function remove(skill: string) {
        onChange(value.filter(item => item !== skill))
        setNotice({ key: 'skills.removed', values: { skill: displaySkillName(skill) } })
    }

    return <fieldset className="skill-picker">
        <legend>{legend}</legend>
        <ul aria-label={selectedLabel}>
            {value.map(skill => <li key={skill}>{displaySkillName(skill)} <button type="button" aria-label={t('skills.removeOne', { skill: displaySkillName(skill) })} onClick={() => remove(skill)}><span aria-hidden="true">×</span></button></li>)}
        </ul>
        <label htmlFor={id}>{inputLabel}</label>
        <div className="skill-input">
            <input ref={input} id={id} value={query} autoComplete="off" aria-describedby={`${id}-help`} onChange={event => {
                const next = event.target.value
                setQuery(next)
                event.target.setCustomValidity(next.trim() ? validationMessage : '')
            }} onKeyDown={event => {
                if (event.key === 'Enter' && !event.nativeEvent.isComposing && event.keyCode !== 229) {
                    event.preventDefault()
                    add(query)
                }
            }} />
            <button type="button" disabled={!query.trim()} onClick={() => add(query)}>{addLabel}</button>
        </div>
        <p id={`${id}-help`}>{help}</p>
        {query.trim() && <ul aria-label={t('skills.suggestions')}>
            {options.slice(0, 8).map(skill => <li key={skill}><button type="button" onClick={() => add(skill, true)}>{skill}</button></li>)}
            {!options.length && <li>{emptyHint}</li>}
        </ul>}
        <p role="status">{notice && t(notice)}</p>
    </fieldset>
}

export default SkillTagPicker

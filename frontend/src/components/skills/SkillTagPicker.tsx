import { useId, useRef, useState } from 'react'
import './SkillTagPicker.css'

const suggestions = ['Python', 'SQL', 'Java', 'JavaScript', 'TypeScript', 'C', 'C++', 'C#', 'Go', 'Rust', 'React', 'Vue', 'Node.js', 'Django', 'FastAPI', 'Spring Boot', 'PostgreSQL', 'MySQL', 'Redis', 'Git', 'Docker', 'Linux', 'AWS', 'PyTorch', 'TensorFlow', 'Machine Learning', 'Data Analysis', 'Excel']
const normalize = (value: string) => value.trim().toLowerCase()

type Props = { value: string[]; onChange: (skills: string[]) => void }

/** 首次填写与编辑共用：搜索预设技能，也可添加自己的标签。 */
function SkillTagPicker({ value, onChange }: Props) {
    const id = useId()
    const input = useRef<HTMLInputElement>(null)
    const [query, setQuery] = useState('')
    const [notice, setNotice] = useState('')
    const options = suggestions.filter(skill => normalize(skill).includes(normalize(query)) && !value.includes(normalize(skill)))

    function add(text: string) {
        const name = normalize(text)
        if (!name) return
        if (!value.includes(name)) onChange([...value, name])
        setNotice(value.includes(name) ? `已选择 ${name}` : `已添加 ${name}`)
        setQuery('')
        input.current?.setCustomValidity('')
        input.current?.focus()
    }

    return <fieldset className="skill-picker">
        <legend>技能（选填）</legend>
        <ul aria-label="已选技能">
            {value.map(skill => <li key={skill}>{skill} <button type="button" aria-label={`移除 ${skill}`} onClick={() => onChange(value.filter(item => item !== skill))}>移除</button></li>)}
        </ul>
        <label htmlFor={id}>搜索或输入技能</label>
        <div className="skill-input">
            <input ref={input} id={id} value={query} autoComplete="off" aria-describedby={`${id}-help`} onChange={event => {
                const next = event.target.value
                setQuery(next)
                event.target.setCustomValidity(next.trim() ? '请先添加此技能，或清空输入后保存。' : '')
            }} onKeyDown={event => {
                if (event.key === 'Enter' && !event.nativeEvent.isComposing && event.keyCode !== 229) {
                    event.preventDefault()
                    add(query)
                }
            }} />
            <button type="button" disabled={!query.trim()} onClick={() => add(query)}>添加技能</button>
        </div>
        <p id={`${id}-help`}>搜索后选择建议，或按 Enter 添加自定义技能。</p>
        {query.trim() && <ul aria-label="技能建议">
            {options.slice(0, 8).map(skill => <li key={skill}><button type="button" onClick={() => add(skill)}>{skill}</button></li>)}
            {!options.length && <li>没有匹配建议，可添加自定义技能。</li>}
        </ul>}
        <p role="status">{notice}</p>
    </fieldset>
}

export default SkillTagPicker

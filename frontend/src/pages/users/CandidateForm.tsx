import { useId, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import type { CandidateProfileCreate } from '../../types'

type CandidateFormProps = {
    submitting: boolean
    submitError: string
    onSubmit: (data: CandidateProfileCreate) => Promise<void>
}

/** 管理候选人输入与动态技能行，将校验后的资料交给页面提交。 */
function CandidateForm({ submitting, submitError, onSubmit }: CandidateFormProps) {
    const formId = useId()
    const nextSkillId = useRef(0)
    const pending = useRef(false)
    const [displayName, setDisplayName] = useState('')
    const [resumeText, setResumeText] = useState('')
    const [skills, setSkills] = useState<{ id: number; value: string }[]>([])
    const [formError, setFormError] = useState('')

    /** 添加有稳定标识的技能输入框，删除其他行时保留现有输入。 */
    function addSkill() {
        const skill = { id: nextSkillId.current++, value: '' }
        setSkills([...skills, skill])
    }

    /** 只修改指定行的技能文字。 */
    function updateSkill(id: number, value: string) {
        setSkills(skills.map(skill => skill.id === id ? { ...skill, value } : skill))
    }

    /** 移除指定技能行，允许全部移除。 */
    function removeSkill(id: number) {
        setSkills(skills.filter(skill => skill.id !== id))
    }

    /** 拒绝空白名称，过滤空技能并防止重复提交，保留简历原文。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (submitting || pending.current) return
        setFormError('')
        const name = displayName.trim()
        if (!name) {
            setFormError('请输入显示名称，不能只填写空格。')
            return
        }

        pending.current = true
        try {
            await onSubmit({
                display_name: name,
                resume_text: resumeText,
                skills: skills.map(skill => skill.value.trim()).filter(Boolean),
            })
        } catch (error) {
            setFormError(error instanceof Error ? error.message : '提交失败，请重试。')
        } finally {
            pending.current = false
        }
    }

    return (
        <form onSubmit={handleSubmit} aria-busy={submitting}>
            <fieldset disabled={submitting} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
                <div style={{ marginBottom: 16 }}>
                    <label htmlFor={`${formId}-name`}>显示名称（必填）</label>
                    <input
                        id={`${formId}-name`}
                        value={displayName}
                        onChange={event => setDisplayName(event.target.value)}
                        required
                        autoComplete="nickname"
                        style={{ display: 'block', width: '100%', boxSizing: 'border-box' }}
                    />
                </div>
                <div style={{ marginBottom: 16 }}>
                    <label htmlFor={`${formId}-resume`}>简历（选填）</label>
                    <textarea
                        id={`${formId}-resume`}
                        value={resumeText}
                        onChange={event => setResumeText(event.target.value)}
                        rows={6}
                        style={{ display: 'block', width: '100%', boxSizing: 'border-box' }}
                    />
                </div>
                <fieldset style={{ margin: '0 0 16px', padding: 12 }}>
                    <legend>技能（选填）</legend>
                    {skills.length === 0 && <p>可以暂不填写技能。</p>}
                    {skills.map((skill, index) => (
                        <div key={skill.id} style={{ marginBottom: 8 }}>
                            <label htmlFor={`${formId}-skill-${skill.id}`}>技能 {index + 1}</label>
                            <div style={{ display: 'flex', gap: 8 }}>
                                <input
                                    id={`${formId}-skill-${skill.id}`}
                                    value={skill.value}
                                    onChange={event => updateSkill(skill.id, event.target.value)}
                                    style={{ flex: 1, minWidth: 0 }}
                                />
                                <button type="button" onClick={() => removeSkill(skill.id)} aria-label={`删除技能 ${index + 1}`}>
                                    删除
                                </button>
                            </div>
                        </div>
                    ))}
                    <button type="button" onClick={addSkill}>添加技能</button>
                </fieldset>
                {formError && <p role="alert" style={{ color: 'var(--text-h)', marginBottom: 8 }}>{formError}</p>}
                {submitError && <p role="alert" style={{ color: 'var(--text-h)', marginBottom: 8 }}>{submitError}</p>}
                <button type="submit">{submitting ? '保存中...' : '保存并继续'}</button>
            </fieldset>
        </form>
    )
}

export default CandidateForm

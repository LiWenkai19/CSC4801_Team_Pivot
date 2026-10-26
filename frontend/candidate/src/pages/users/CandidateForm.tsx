import { useId, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import type { CandidateProfileCreate, CandidateProfilePublic } from '../../types'
import { SkillTagPicker } from '../../components/skills/SkillTagPicker'
import { uniqueSkills } from '../../components/skills/skillCatalog'

type CandidateFormProps = {
    initialProfile?: CandidateProfilePublic
    submitLabel?: string
    submitting: boolean
    submitError: string
    onSubmit: (data: CandidateProfileCreate) => Promise<void>
}

/** 管理候选人资料及技能标签，将校验后的资料交给页面提交。 */
function CandidateForm({ initialProfile, submitLabel = '保存并继续', submitting, submitError, onSubmit }: CandidateFormProps) {
    const formId = useId()
    const pending = useRef(false)
    const [displayName, setDisplayName] = useState(initialProfile?.display_name ?? '')
    const [resumeText, setResumeText] = useState(initialProfile?.resume_text ?? '')
    const [skills, setSkills] = useState<string[]>(() => uniqueSkills(initialProfile?.skills ?? []))
    const [formError, setFormError] = useState('')

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
                skills: uniqueSkills(skills),
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
                <SkillTagPicker value={skills} onChange={setSkills} disabled={submitting} />
                {formError && <p role="alert" style={{ color: 'var(--text-h)', marginBottom: 8 }}>{formError}</p>}
                {submitError && <p role="alert" style={{ color: 'var(--text-h)', marginBottom: 8 }}>{submitError}</p>}
                <button type="submit">{submitting ? '保存中...' : submitLabel}</button>
            </fieldset>
        </form>
    )
}

export default CandidateForm

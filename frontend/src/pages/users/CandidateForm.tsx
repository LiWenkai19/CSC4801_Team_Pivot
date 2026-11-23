import { useId, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import type { CandidateProfileCreate } from '../../types'
import CandidateSkillPicker from '../../components/skills/CandidateSkillPicker'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'

type CandidateFormProps = {
    submitting: boolean
    submitError: MessageKey | ''
    onSubmit: (data: CandidateProfileCreate) => Promise<void>
}

/** 管理候选人输入，将校验后的资料交给页面提交。 */
function CandidateForm({ submitting, submitError, onSubmit }: CandidateFormProps) {
    const { t } = useLanguage()
    const formId = useId()
    const pending = useRef(false)
    const [displayName, setDisplayName] = useState('')
    const [resumeText, setResumeText] = useState('')
    const [skills, setSkills] = useState<string[]>([])
    const [formError, setFormError] = useState<MessageKey | ''>('')

    /** 拒绝空白名称，过滤空技能并防止重复提交，保留简历原文。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (submitting || pending.current) return
        setFormError('')
        const name = displayName.trim()
        if (!name) {
            setFormError('profile.nameWhitespace')
            return
        }

        pending.current = true
        try {
            await onSubmit({
                display_name: name,
                resume_text: resumeText,
                skills,
            })
        } catch (error) {
            setFormError(apiFeedback(error, 'common.submitFailed'))
        } finally {
            pending.current = false
        }
    }

    return (
        <form className="form-panel" onSubmit={handleSubmit} aria-busy={submitting}>
            <fieldset disabled={submitting}>
                <div className="field">
                    <label htmlFor={`${formId}-name`}>{t('profile.name')}</label>
                    <input
                        id={`${formId}-name`}
                        value={displayName}
                        onChange={event => setDisplayName(event.target.value)}
                        required
                        autoComplete="nickname"
                    />
                </div>
                <div className="field">
                    <label htmlFor={`${formId}-resume`}>{t('profile.resume')}</label>
                    <textarea
                        id={`${formId}-resume`}
                        value={resumeText}
                        onChange={event => setResumeText(event.target.value)}
                        rows={6}
                    />
                </div>
                <CandidateSkillPicker value={skills} onChange={setSkills} />
                {formError && <p className="feedback" role="alert">{t(formError)}</p>}
                {submitError && <p className="feedback" role="alert">{t(submitError)}</p>}
                <button type="submit">{submitting ? t('common.saving') : t('common.saveAndContinue')}</button>
            </fieldset>
        </form>
    )
}

export default CandidateForm

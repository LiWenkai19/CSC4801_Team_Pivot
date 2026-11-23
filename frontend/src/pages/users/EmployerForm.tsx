import { useId, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import type { EmployerProfileCreate } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'

type EmployerFormProps = {
    submitting: boolean
    submitError: MessageKey | ''
    onSubmit: (data: EmployerProfileCreate) => Promise<void>
}

/** 管理公司资料输入，将校验后的内容交给页面提交。 */
function EmployerForm({ submitting, submitError, onSubmit }: EmployerFormProps) {
    const { t } = useLanguage()
    const formId = useId()
    const pending = useRef(false)
    const [companyName, setCompanyName] = useState('')
    const [companyDescription, setCompanyDescription] = useState('')
    const [formError, setFormError] = useState<MessageKey | ''>('')

    /** 拒绝空白公司名称，保留描述原文并防止重复提交。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (submitting || pending.current) return
        setFormError('')
        const name = companyName.trim()
        if (!name) {
            setFormError('company.nameRequired')
            return
        }

        pending.current = true
        try {
            await onSubmit({
                company_name: name,
                company_description: companyDescription,
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
                    <label htmlFor={`${formId}-company-name`}>{t('company.name')}</label>
                    <input
                        id={`${formId}-company-name`}
                        value={companyName}
                        onChange={event => setCompanyName(event.target.value)}
                        required
                        autoComplete="organization"
                    />
                </div>
                <div className="field">
                    <label htmlFor={`${formId}-company-description`}>{t('company.descriptionOptional')}</label>
                    <textarea
                        id={`${formId}-company-description`}
                        value={companyDescription}
                        onChange={event => setCompanyDescription(event.target.value)}
                        rows={6}
                    />
                </div>
                {formError && <p className="feedback" role="alert">{t(formError)}</p>}
                {submitError && <p className="feedback" role="alert">{t(submitError)}</p>}
                <button type="submit">{submitting ? t('common.saving') : t('common.saveAndContinue')}</button>
            </fieldset>
        </form>
    )
}

export default EmployerForm

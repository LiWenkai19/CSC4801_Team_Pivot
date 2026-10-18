import { useId, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import type { EmployerProfileCreate } from '../../types'

type EmployerFormProps = {
    submitting: boolean
    submitError: string
    onSubmit: (data: EmployerProfileCreate) => Promise<void>
}

/** 管理公司资料输入，将校验后的内容交给页面提交。 */
function EmployerForm({ submitting, submitError, onSubmit }: EmployerFormProps) {
    const formId = useId()
    const pending = useRef(false)
    const [companyName, setCompanyName] = useState('')
    const [companyDescription, setCompanyDescription] = useState('')
    const [formError, setFormError] = useState('')

    /** 拒绝空白公司名称，保留描述原文并防止重复提交。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (submitting || pending.current) return
        setFormError('')
        const name = companyName.trim()
        if (!name) {
            setFormError('请输入公司名称，不能只填写空格。')
            return
        }

        pending.current = true
        try {
            await onSubmit({
                company_name: name,
                company_description: companyDescription,
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
                    <label htmlFor={`${formId}-company-name`}>公司名称（必填）</label>
                    <input
                        id={`${formId}-company-name`}
                        value={companyName}
                        onChange={event => setCompanyName(event.target.value)}
                        required
                        autoComplete="organization"
                        style={{ display: 'block', width: '100%', boxSizing: 'border-box' }}
                    />
                </div>
                <div style={{ marginBottom: 16 }}>
                    <label htmlFor={`${formId}-company-description`}>公司描述（选填）</label>
                    <textarea
                        id={`${formId}-company-description`}
                        value={companyDescription}
                        onChange={event => setCompanyDescription(event.target.value)}
                        rows={6}
                        style={{ display: 'block', width: '100%', boxSizing: 'border-box' }}
                    />
                </div>
                {formError && <p role="alert" style={{ color: 'var(--text-h)', marginBottom: 8 }}>{formError}</p>}
                {submitError && <p role="alert" style={{ color: 'var(--text-h)', marginBottom: 8 }}>{submitError}</p>}
                <button type="submit">{submitting ? '保存中...' : '保存并继续'}</button>
            </fieldset>
        </form>
    )
}

export default EmployerForm

import { useId, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import type { CandidateProfileCreate, CandidateProfilePublic } from '../../types'
import { SkillTagPicker } from '../../components/skills/SkillTagPicker'
import { uniqueSkills } from '../../components/skills/skillCatalog'

// 父页面负责提交；表单负责收集输入与基础校验，initialProfile 用于编辑已有资料。
type CandidateFormProps = {
    initialProfile?: CandidateProfilePublic
    submitLabel?: string
    submitting: boolean
    submitError: string
    onSubmit: (data: CandidateProfileCreate) => Promise<void>
}

/** 管理候选人资料及技能标签，将校验后的资料交给页面提交。 */
function CandidateForm({ initialProfile, submitLabel = '保存并继续', submitting, submitError, onSubmit }: CandidateFormProps) {
    // useId 关联 label 与输入框；pending 防止 React 重新渲染前的快速重复提交。
    const formId = useId()
    const pending = useRef(false)
    // 编辑时从已有资料初始化；首次填写时使用空值。技能初始化时先规范化去重。
    const [displayName, setDisplayName] = useState(initialProfile?.display_name ?? '')
    const [resumeText, setResumeText] = useState(initialProfile?.resume_text ?? '')
    const [skills, setSkills] = useState<string[]>(() => uniqueSkills(initialProfile?.skills ?? []))
    const [formError, setFormError] = useState('')

    /** 拒绝空白名称，过滤空技能并防止重复提交，保留简历原文。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        // 阻止浏览器默认刷新页面，提交中或尚未结束的请求不再发起第二次。
        event.preventDefault()
        if (submitting || pending.current) return
        setFormError('')
        // 显示名称去首尾空格并拒绝纯空白；简历文本则按原样保留。
        const name = displayName.trim()
        if (!name) {
            setFormError('请输入显示名称，不能只填写空格。')
            return
        }

        // 将字段交给父页面；不论请求成功还是失败，finally 都会恢复提交锁。
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

    // fieldset 在提交期间禁用控件；SkillTagPicker 的变化同步写入 skills 状态。
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

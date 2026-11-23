import { useRef, useState } from 'react'
import { ApiError } from '../../api/common_api'
import { applyToJob } from '../../api/candidate_api'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'

/** 列表与详情共用投递行为；409 同步已申请状态，反馈在刷新后仍可见。 */
function ApplyButton({ jobId, applied }: { jobId: string; applied: boolean }) {
    const { t } = useLanguage()
    const [done, setDone] = useState(false)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState<MessageKey | ''>('')
    const pending = useRef(false)
    async function apply() {
        if (pending.current || applied || done) return
        pending.current = true
        setSubmitting(true)
        setError('')
        try {
            await applyToJob(jobId)
            setDone(true)
        } catch (reason) {
            if (reason instanceof ApiError && reason.status === 409 && reason.message === 'Already applied') setDone(true)
            else setError(apiFeedback(reason, 'applying.failed'))
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }
    return <div className="apply-action record-stack">
        <button className="button-primary" type="button" disabled={applied || done || submitting} onClick={apply}>{applied || done ? t('applying.applied') : submitting ? t('applying.submitting') : t('applying.cta')}</button>
        {(applied || done) && <p className="apply-notice" role="status">{t('applying.notice')}</p>}
        {error && <p className="feedback" role="alert">{t(error)} {t('applying.retryHint')}</p>}
    </div>
}

export default ApplyButton

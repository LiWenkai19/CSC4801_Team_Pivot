import { useRef, useState } from 'react'
import { ApiError } from '../../api/common_api'
import { applyToJob } from '../../api/candidate_api'

/** 列表与详情共用投递行为；409 同步已申请状态，反馈在刷新后仍可见。 */
function ApplyButton({ jobId, applied }: { jobId: string; applied: boolean }) {
    const [done, setDone] = useState(false)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState('')
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
            else setError(reason instanceof Error ? reason.message : '申请失败，请重试。')
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }
    return <div>
        <button type="button" disabled={applied || done || submitting} onClick={apply}>{applied || done ? '已申请' : submitting ? '提交中...' : '申请职位'}</button>
        {(applied || done) && <p role="status">你已申请该职位，请勿重复申请。</p>}
        {error && <p role="alert">{error} 请重试；如已提交成功，重试会同步申请状态。</p>}
    </div>
}

export default ApplyButton

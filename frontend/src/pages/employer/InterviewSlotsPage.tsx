import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/common_api'
import { createInterviewSlot, deleteInterviewSlot, listMyInterviewSlots } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'
import type { ManagedInterviewSlot } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'
import { formatShanghaiTime } from '../../i18n/dates'

const slotDurationMinutes = 30

type SlotAction = { kind: 'create' } | { kind: 'delete'; slotId: string }

/** 雇主查看尚未开始的时段，管理其中未预约的时段。 */
function InterviewSlotsPage() {
    const { locale, t } = useLanguage()
    const { currentUser } = useAuth()
    const isEmployer = currentUser?.role === 'employer'
    const [slots, setSlots] = useState<ManagedInterviewSlot[]>([])
    const [startTime, setStartTime] = useState('')
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<MessageKey | ''>('')
    const [actionError, setActionError] = useState<MessageKey | ''>('')
    const [notice, setNotice] = useState<MessageKey | ''>('')
    const [action, setAction] = useState<SlotAction | null>(null)
    const [attempt, setAttempt] = useState(0)
    const pending = useRef(false)

    // 预览与提交使用同一个上海时间；最终结束时间由服务端计算。
    const startsAt = `${startTime}+08:00`
    const startTimestamp = Date.parse(startsAt)
    const endTime = Number.isFinite(startTimestamp) ? new Date(startTimestamp + slotDurationMinutes * 60_000) : null

    useEffect(() => {
        if (!isEmployer) return
        let active = true
        listMyInterviewSlots()
            .then(data => { if (active) setSlots(data) })
            .catch(reason => {
                if (active) setLoadError(apiFeedback(reason, 'slots.loadFailed'))
            })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [isEmployer, attempt])

    /** 从服务器刷新时段和预约状态，处理其他会话产生的预约或删除。 */
    function reloadSlots() {
        setLoading(true)
        setLoadError('')
        setAttempt(previous => previous + 1)
    }

    /** 将表单中的上海时间提交为带偏移量的开始时间。 */
    async function handleCreate(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (loading || pending.current) return
        setNotice('')
        setActionError('')
        if (!Number.isFinite(startTimestamp) || startTimestamp <= Date.now()) {
            setActionError('slots.future')
            return
        }
        pending.current = true
        setAction({ kind: 'create' })
        try {
            await createInterviewSlot(startsAt)
            setStartTime('')
            setNotice('slots.created')
            reloadSlots()
        } catch (reason) {
            if (reason instanceof ApiError && reason.status === 409) {
                setActionError('slots.overlap')
                reloadSlots()
            } else {
                setActionError(apiFeedback(reason, 'slots.createFailed'))
            }
        } finally {
            pending.current = false
            setAction(null)
        }
    }

    /** 删除成功后刷新列表。如果时段已被占用或移除，也同步最新列表。 */
    async function handleDelete(slot: ManagedInterviewSlot) {
        if (slot.is_booked || loading || pending.current) return
        const slotId = slot.id
        pending.current = true
        setAction({ kind: 'delete', slotId })
        setNotice('')
        setActionError('')
        try {
            await deleteInterviewSlot(slotId)
            setNotice('slots.deleted')
            reloadSlots()
        } catch (reason) {
            if (reason instanceof ApiError && (reason.status === 409 || reason.status === 404)) {
                setActionError(reason.status === 409 ? 'slots.deleteConflict' : 'api.slotMissing')
                reloadSlots()
            } else {
                setActionError(apiFeedback(reason, 'common.deleteFailed'))
            }
        } finally {
            pending.current = false
            setAction(null)
        }
    }

    if (!isEmployer) return <main className="work-page"><p className="feedback" role="alert">{t('auth.employerOnly')}</p><Link to="/navpage">{t('common.home')}</Link></main>

    return <main className="work-page">
        <nav className="page-nav" aria-label={t('slots.nav')}>
            <Link to="/navpage">{t('common.home')}</Link>
            <Link to="/employer/jobs">{t('jobs.list')}</Link>
        </nav>
        <h1>{t('slots.title')}</h1>
        <form className="form-panel slot-form" onSubmit={handleCreate}>
            <div className="field">
                <label htmlFor="interview-start-time">{t('slots.start')}</label>
                <div className="slot-time-field">
                    <input
                        id="interview-start-time"
                        type="datetime-local"
                        value={startTime}
                        onChange={event => setStartTime(event.target.value)}
                        disabled={action !== null}
                        aria-describedby="interview-end-time"
                        required
                    />
                    <output id="interview-end-time" htmlFor="interview-start-time">
                        <span>{t('slots.end')}</span>
                        {endTime ? <time dateTime={endTime.toISOString()}>{formatShanghaiTime(endTime, locale)}</time> : '—'}
                    </output>
                </div>
            </div>
            <button type="submit" disabled={loading || action !== null}>
                {action?.kind === 'create' ? t('slots.creating') : t('slots.createDuration', { minutes: slotDurationMinutes })}
            </button>
        </form>
        {actionError && <p className="feedback" role="alert">{t(actionError)}</p>}
        {notice && <p className="feedback" role="status">{t(notice)}</p>}
        <section className="page-section" aria-labelledby="interview-slot-list">
            <header className="section-heading">
                <h2 id="interview-slot-list">{t('slots.list')}</h2>
                <button type="button" onClick={reloadSlots} disabled={loading || action !== null}>{t('slots.refresh')}</button>
            </header>
            {loading && <p className="feedback" role="status">{t('slots.loading')}</p>}
            {loadError && <p className="feedback" role="alert">{t(loadError)}</p>}
            {!loading && !loadError && (slots.length === 0 ? <p className="panel empty-state">{t('slots.empty')}</p> : <ul className="records" role="list">
                {slots.map(slot => <li className="section-heading" key={slot.id}>
                    <div className="record-stack">
                        <p><time dateTime={slot.starts_at}>{formatShanghaiTime(slot.starts_at, locale)}</time>
                        {' – '}
                        <time dateTime={slot.ends_at}>{formatShanghaiTime(slot.ends_at, locale)}</time></p>
                        <div className="slot-status-line">
                            <span className="status-chip">{slot.is_booked ? t('slots.booked') : t('slots.unbooked')}</span>
                            {slot.is_booked && slot.job_id && <>
                                {slot.application_id && <Link className="status-chip" to={`/employer/jobs/${slot.job_id}#application-${slot.application_id}`}>{t('slots.applicant', { name: slot.applicant_name ?? '—' })}</Link>}
                                <Link className="status-chip" to={`/employer/jobs/${slot.job_id}`}>{t('slots.job', { jobTitle: slot.job_title ?? slot.job_id })}</Link>
                            </>}
                        </div>
                    </div>
                    <button className="button-danger" type="button" onClick={() => handleDelete(slot)} disabled={slot.is_booked || action !== null}>
                        {action?.kind === 'delete' && action.slotId === slot.id ? t('common.deleting') : t('common.delete')}
                    </button>
                </li>)}
            </ul>)}
        </section>
    </main>
}

export default InterviewSlotsPage

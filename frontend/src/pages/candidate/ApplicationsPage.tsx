import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { bookSlot, listApplications, listAvailableSlots } from '../../api/candidate_api'
import type { BookingPublic, CandidateApplication, InterviewSlot } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'
import { formatShanghaiTime } from '../../i18n/dates'

/** 每份申请独立管理时段请求，避免不同申请的加载结果互相覆盖。 */
function BookingForm({ applicationId, onBooked, onRefresh }: { applicationId: string; onBooked: (booking: BookingPublic) => void; onRefresh: () => void }) {
    const { locale, t } = useLanguage()
    const [slots, setSlots] = useState<InterviewSlot[] | null>(null)
    const [selected, setSelected] = useState('')
    const [loading, setLoading] = useState(false)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<MessageKey | ''>('')
    const pending = useRef(false)
    async function load() {
        if (pending.current) return
        pending.current = true
        setLoading(true)
        setError('')
        try {
            const rows = await listAvailableSlots(applicationId)
            setSlots(rows)
            setSelected('')
        } catch (reason) { setError(apiFeedback(reason, 'booking.loadFailed')) }
        finally { pending.current = false; setLoading(false) }
    }
    async function book() {
        if (pending.current || !selected) return
        pending.current = true
        setSaving(true)
        setError('')
        try { onBooked(await bookSlot(applicationId, selected)) }
        catch (reason) {
            setError(apiFeedback(reason, 'booking.failed'))
            setSlots(null)
            setSelected('')
        } finally { pending.current = false; setSaving(false) }
    }
    return <div className="page-section">
        <button type="button" disabled={loading || saving} onClick={load}>{loading ? t('common.loading') : t('booking.loadSlots')}</button>
        {error && <div className="record-stack"><p className="feedback" role="alert">{t(error)}</p><div><button type="button" onClick={onRefresh}>{t('applications.refresh')}</button></div></div>}
        {slots && (slots.length === 0 ? <p>{t('booking.noSlots')}</p> : <div className="booking-controls">
            <label htmlFor={`slot-${applicationId}`}>{t('booking.select')}</label>
            <select id={`slot-${applicationId}`} value={selected} disabled={saving || loading} onChange={event => setSelected(event.target.value)}>
                <option value="">{t('booking.choose')}</option>
                {slots.map(slot => <option key={slot.id} value={slot.id}>{formatShanghaiTime(slot.starts_at, locale)} – {formatShanghaiTime(slot.ends_at, locale)}</option>)}
            </select>
            <button className="button-primary" type="button" disabled={!selected || saving || loading} onClick={book}>{saving ? t('booking.booking') : t('booking.confirm')}</button>
        </div>)}
    </div>
}

/** 状态及预约来自同一共享记录，候选人不能修改申请状态。 */
function ApplicationsPage() {
    const { locale, t } = useLanguage()
    const [rows, setRows] = useState<CandidateApplication[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<MessageKey | ''>('')
    const [attempt, setAttempt] = useState(0)
    function refresh() { setLoading(true); setError(''); setAttempt(value => value + 1) }
    useEffect(() => {
        let active = true
        listApplications().then(data => { if (active) setRows(data) })
            .catch(reason => { if (active) setError(apiFeedback(reason, 'applications.loadFailed')) })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [attempt])
    return <>
        <header className="section-heading candidate-toolbar">
            <div><h1>{t('applications.title')}</h1><p className="page-intro">{t('booking.timezoneNote')}</p></div>
            <button type="button" disabled={loading} onClick={refresh}>{t('applications.refresh')}</button>
        </header>
        {loading && <p className="feedback" role="status">{t('applications.loading')}</p>}
        {error && <p className="feedback" role="alert">{t(error)} {t('applications.retry')}</p>}
        {!loading && !error && (rows.length === 0 ? <p className="panel empty-state">{t('applications.empty')} <Link to="/candidate/jobs">{t('applications.browse')}</Link></p> : <ul className="records" role="list">
            {rows.map(row => <li key={row.application_id} className="record-stack">
                <h2><Link className="record-title" to={`/candidate/jobs/${row.job_id}`}>{row.job_title}</Link></h2>
                <p className="record-meta">{t('common.companyValue', { name: row.company_name })}</p><p className="status-chip">{t('applications.statusValue', { status: t(`status.${row.status}`) })}</p>
                {row.booking ? <p className="feedback" role="status">{t('booking.bookedLabel')}<time dateTime={row.booking.starts_at}>{formatShanghaiTime(row.booking.starts_at, locale)}</time> – <time dateTime={row.booking.ends_at}>{formatShanghaiTime(row.booking.ends_at, locale)}</time></p>
                    : row.status === 'Interviewing' ? <BookingForm applicationId={row.application_id} onRefresh={refresh} onBooked={booking => setRows(previous => previous.map(item => item.application_id === row.application_id ? { ...item, booking } : item))} />
                    : <p>{t('booking.noBooking')}</p>}
            </li>)}
        </ul>)}
    </>
}

export default ApplicationsPage

import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { bookSlot, listApplications, listAvailableSlots } from '../../api/candidate_api'
import type { BookingPublic, CandidateApplication, InterviewSlot } from '../../types'

const statuses = { Pending: '待处理', Interviewing: '面试中', Rejected: '已拒绝', Accepted: '已录用' }
const displayTime = (value: string) => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'medium', timeStyle: 'short', hour12: false }).format(new Date(value))

/** 每份申请独立管理时段请求，避免不同申请的加载结果互相覆盖。 */
function BookingForm({ applicationId, onBooked, onRefresh }: { applicationId: string; onBooked: (booking: BookingPublic) => void; onRefresh: () => void }) {
    const [slots, setSlots] = useState<InterviewSlot[] | null>(null)
    const [selected, setSelected] = useState('')
    const [loading, setLoading] = useState(false)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState('')
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
        } catch (reason) { setError(reason instanceof Error ? reason.message : '时段加载失败，请重试。') }
        finally { pending.current = false; setLoading(false) }
    }
    async function book() {
        if (pending.current || !selected) return
        pending.current = true
        setSaving(true)
        setError('')
        try { onBooked(await bookSlot(applicationId, selected)) }
        catch (reason) {
            setError(reason instanceof Error && reason.message === 'Slot already booked'
                ? '该时段已被预约，请重新加载并选择其他时段。'
                : reason instanceof Error ? `${reason.message}。请刷新申请后重试。` : '预约失败，请刷新申请。')
            setSlots(null)
            setSelected('')
        } finally { pending.current = false; setSaving(false) }
    }
    return <div>
        <button type="button" disabled={loading || saving} onClick={load}>{loading ? '加载中...' : '加载可预约时段'}</button>
        {error && <div><p role="alert">{error}</p><button type="button" onClick={onRefresh}>刷新申请</button></div>}
        {slots && (slots.length === 0 ? <p>暂无可预约时段，请稍后重新加载。</p> : <div className="booking-controls">
            <label htmlFor={`slot-${applicationId}`}>选择面试时段（上海时间）</label>
            <select id={`slot-${applicationId}`} value={selected} disabled={saving || loading} onChange={event => setSelected(event.target.value)}>
                <option value="">请选择时段</option>
                {slots.map(slot => <option key={slot.id} value={slot.id}>{displayTime(slot.starts_at)} – {displayTime(slot.ends_at)}</option>)}
            </select>
            <button type="button" disabled={!selected || saving || loading} onClick={book}>{saving ? '预约中...' : '确认预约'}</button>
        </div>)}
    </div>
}

/** 状态及预约来自同一共享记录，候选人不能修改申请状态。 */
function ApplicationsPage() {
    const [rows, setRows] = useState<CandidateApplication[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [attempt, setAttempt] = useState(0)
    function refresh() { setLoading(true); setError(''); setAttempt(value => value + 1) }
    useEffect(() => {
        let active = true
        listApplications().then(data => { if (active) setRows(data) })
            .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : '申请加载失败。') })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [attempt])
    return <>
        <h1>我的申请</h1><p>面试时间均为上海时间（UTC+8）。</p>
        <button type="button" disabled={loading} onClick={refresh}>刷新申请</button>
        {loading && <p role="status">正在加载申请...</p>}
        {error && <p role="alert">{error} 请刷新申请重试。</p>}
        {!loading && !error && (rows.length === 0 ? <p>暂无申请，前往<Link to="/candidate/jobs">职位推荐</Link>开始投递。</p> : <ul className="records">
            {rows.map(row => <li key={row.application_id}>
                <h2><Link to={`/candidate/jobs/${row.job_id}`}>{row.job_title}</Link></h2>
                <p>公司：{row.company_name}</p><p>申请状态：{statuses[row.status]}</p>
                {row.booking ? <p role="status">面试已预约：<time dateTime={row.booking.starts_at}>{displayTime(row.booking.starts_at)}</time> – <time dateTime={row.booking.ends_at}>{displayTime(row.booking.ends_at)}</time>（上海时间）</p>
                    : row.status === 'Interviewing' ? <BookingForm applicationId={row.application_id} onRefresh={refresh} onBooked={booking => setRows(previous => previous.map(item => item.application_id === row.application_id ? { ...item, booking } : item))} />
                    : <p>暂无面试预约。</p>}
            </li>)}
        </ul>)}
    </>
}

export default ApplicationsPage

import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/common_api'
import { createInterviewSlot, deleteInterviewSlot, listMyInterviewSlots } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'
import type { ManagedInterviewSlot } from '../../types'

const slotTime = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    dateStyle: 'medium',
    timeStyle: 'short',
    hour12: false,
})
const slotDurationMinutes = 30

type SlotAction = { kind: 'create' } | { kind: 'delete'; slotId: string }

/** 雇主查看尚未开始的时段，管理其中未预约的时段。 */
function InterviewSlotsPage() {
    const { currentUser } = useAuth()
    const isEmployer = currentUser?.role === 'employer'
    const [slots, setSlots] = useState<ManagedInterviewSlot[]>([])
    const [startTime, setStartTime] = useState('')
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState('')
    const [actionError, setActionError] = useState('')
    const [notice, setNotice] = useState('')
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
                if (active) setLoadError(reason instanceof Error ? reason.message : '加载失败，请刷新重试。')
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
            setActionError('请选择未来的开始时间。')
            return
        }
        pending.current = true
        setAction({ kind: 'create' })
        try {
            await createInterviewSlot(startsAt)
            setStartTime('')
            setNotice('已创建面试时段。')
            reloadSlots()
        } catch (reason) {
            if (reason instanceof ApiError && reason.status === 409) {
                setActionError('与已有面试时段重叠，请选择其他开始时间。')
                reloadSlots()
            } else {
                setActionError(reason instanceof Error ? reason.message : '创建失败，请重试。')
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
            setNotice('已删除面试时段。')
            reloadSlots()
        } catch (reason) {
            if (reason instanceof ApiError && (reason.status === 409 || reason.status === 404)) {
                setActionError(reason.status === 409 ? '时段已被预约或已开始，无法删除。' : '该时段已不存在。')
                reloadSlots()
            } else {
                setActionError(reason instanceof Error ? reason.message : '删除失败，请重试。')
            }
        } finally {
            pending.current = false
            setAction(null)
        }
    }

    if (!isEmployer) return <main className="work-page"><p className="feedback" role="alert">仅雇主可访问此页面。</p><Link to="/navpage">返回主页</Link></main>

    return <main className="work-page">
        <nav className="page-nav" aria-label="面试时段导航">
            <Link to="/navpage">返回主页</Link>
            <Link to="/employer/jobs">职位列表</Link>
        </nav>
        <h1>面试时段</h1>
        <form className="form-panel slot-form" onSubmit={handleCreate}>
            <div className="field">
                <label htmlFor="interview-start-time">开始时间（上海时间 UTC+8）</label>
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
                        <span>结束时间</span>
                        {endTime ? <time dateTime={endTime.toISOString()}>{slotTime.format(endTime)}</time> : '—'}
                    </output>
                </div>
            </div>
            <button type="submit" disabled={loading || action !== null}>
                {action?.kind === 'create' ? '创建中...' : `创建 ${slotDurationMinutes} 分钟时段`}
            </button>
        </form>
        {actionError && <p className="feedback" role="alert">{actionError}</p>}
        {notice && <p className="feedback" role="status">{notice}</p>}
        <section className="page-section" aria-labelledby="interview-slot-list">
            <header className="section-heading">
                <h2 id="interview-slot-list">时段列表</h2>
                <button type="button" onClick={reloadSlots} disabled={loading || action !== null}>刷新时段</button>
            </header>
            {loading && <p className="feedback" role="status">正在加载时段...</p>}
            {loadError && <p className="feedback" role="alert">{loadError}</p>}
            {!loading && !loadError && (slots.length === 0 ? <p className="panel empty-state">暂无未开始的面试时段。</p> : <ul className="records" role="list">
                {slots.map(slot => <li className="section-heading" key={slot.id}>
                    <div className="record-stack">
                        <p><time dateTime={slot.starts_at}>{slotTime.format(new Date(slot.starts_at))}</time>
                        {' – '}
                        <time dateTime={slot.ends_at}>{slotTime.format(new Date(slot.ends_at))}</time></p>
                        <span className="status-chip">{slot.is_booked ? '已预约' : '未预约'}</span>
                    </div>
                    <button className="button-danger" type="button" onClick={() => handleDelete(slot)} disabled={slot.is_booked || action !== null}>
                        {action?.kind === 'delete' && action.slotId === slot.id ? '删除中...' : '删除'}
                    </button>
                </li>)}
            </ul>)}
        </section>
    </main>
}

export default InterviewSlotsPage

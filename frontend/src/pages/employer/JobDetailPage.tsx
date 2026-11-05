import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { changeApplicationStatus, getMyJob, listJobApplicants } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'
import type { ApplicantPublic, ApplicationStatus, JobPublic } from '../../types'

const statuses: ApplicationStatus[] = ['Pending', 'Interviewing', 'Rejected', 'Accepted']

/** 预约统一显示 UTC；兼容本地测试库返回不带偏移的 UTC 时间。 */
function bookingTime(value: string): string {
    const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
    return `${new Date(timestamp).toLocaleString('zh-CN', { timeZone: 'UTC', hour12: false })} UTC`
}

/** 每行独立提交状态，失败保留选择，不改变已保存状态或预约。 */
function ApplicantRow({ applicant, onUpdated }: { applicant: ApplicantPublic; onUpdated: (id: string, status: ApplicationStatus) => void }) {
    const [selected, setSelected] = useState<ApplicationStatus>(applicant.status)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState('')
    const [notice, setNotice] = useState('')
    const pending = useRef(false)

    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (pending.current) return
        pending.current = true
        setSubmitting(true)
        setError('')
        setNotice('')
        try {
            const saved = await changeApplicationStatus(applicant.application_id, { status: selected })
            onUpdated(saved.application_id, saved.status)
            setSelected(saved.status)
            setNotice('状态已保存')
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : '状态保存失败，请重试。')
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }

    return <tr>
        <th scope="row" style={{ textAlign: 'left', overflowWrap: 'anywhere' }}>{applicant.display_name}<br /><small>{applicant.candidate_id}</small></th>
        <td>{applicant.skills.join(', ') || '无'}</td>
        <td>{applicant.match_score}</td>
        <td>
            <p>当前状态：{applicant.status}</p>
            <form onSubmit={handleSubmit} aria-busy={submitting}>
                <select aria-label={`${applicant.display_name}的申请状态`} value={selected} disabled={submitting} onChange={event => {
                    const status = statuses.find(value => value === event.target.value)
                    if (status) setSelected(status)
                    setNotice('')
                }}>
                    {statuses.map(status => <option key={status} value={status}>{status}</option>)}
                </select>{' '}
                <button type="submit" disabled={submitting}>{submitting ? '保存中...' : '保存状态'}</button>
            </form>
            {error && <p role="alert">{error} · <Link to="/employer/jobs">返回职位列表</Link></p>}
            {notice && <p role="status">{notice}</p>}
        </td>
        <td>{applicant.booking ? <>
            <time dateTime={applicant.booking.starts_at}>{bookingTime(applicant.booking.starts_at)}</time><br />至<br />
            <time dateTime={applicant.booking.ends_at}>{bookingTime(applicant.booking.ends_at)}</time>
        </> : '无'}</td>
    </tr>
}

/** 职位与申请人分别显示加载结果，沿用后端匹配分及平级排序。 */
function JobDetailPage() {
    const { jobId } = useParams<{ jobId: string }>()
    return <JobDetail key={jobId} jobId={jobId} />
}

/** 地址变化时隔离上一个职位的加载结果与申请行状态。 */
function JobDetail({ jobId }: { jobId: string | undefined }) {
    const { currentUser } = useAuth()
    const isEmployer = currentUser?.role === 'employer'
    const [job, setJob] = useState<JobPublic | null>(null)
    const [applicants, setApplicants] = useState<ApplicantPublic[]>([])
    const [loading, setLoading] = useState(true)
    const [jobError, setJobError] = useState('')
    const [applicantsError, setApplicantsError] = useState('')
    const [attempt, setAttempt] = useState(0)

    useEffect(() => {
        if (!isEmployer || !jobId) return
        let active = true
        Promise.allSettled([getMyJob(jobId), listJobApplicants(jobId)]).then(([jobResult, applicantsResult]) => {
            if (!active) return
            if (jobResult.status === 'fulfilled') setJob(jobResult.value)
            else setJobError(jobResult.reason instanceof Error ? jobResult.reason.message : '职位加载失败，请重试。')
            if (applicantsResult.status === 'fulfilled') setApplicants(applicantsResult.value)
            else setApplicantsError(applicantsResult.reason instanceof Error ? applicantsResult.reason.message : '申请人加载失败，请重试。')
        }).finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [isEmployer, jobId, attempt])

    function retryLoad() {
        setLoading(true)
        setJob(null)
        setApplicants([])
        setJobError('')
        setApplicantsError('')
        setAttempt(previous => previous + 1)
    }

    function updateStatus(id: string, status: ApplicationStatus) {
        setApplicants(previous => previous.map(applicant => applicant.application_id === id ? { ...applicant, status } : applicant))
    }

    if (!isEmployer) return <main><p role="alert">仅雇主可访问此页面。</p><Link to="/navpage">返回主页</Link></main>
    return <main style={{ width: '100%', padding: 20, boxSizing: 'border-box', textAlign: 'left' }}>
        <h1>职位详情与申请人</h1>
        <Link to="/employer/jobs">返回职位列表</Link>
        {loading && <p role="status">正在加载职位与申请人...</p>}
        {jobError && <p role="alert">{jobError}</p>}
        {applicantsError && <p role="alert">{applicantsError}</p>}
        {!loading && (jobError || applicantsError) && <button type="button" onClick={retryLoad}>重新加载</button>}
        {!loading && job && <>
            <section aria-label="职位信息" style={{ margin: '20px 0' }}>
                <h2>{job.title}</h2>
                <p>公司：{job.company_name}</p>
                <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{job.description}</p>
                <p>所需技能：{job.required_skills.join(', ') || '无'}</p>
                <p>创建时间：<time dateTime={job.created_at}>{job.created_at}</time></p>
                <Link to={`/employer/jobs/${job.id}/edit`}>编辑职位</Link>
            </section>
            <section aria-label="申请人列表">
                <h2>申请人（按匹配分从高到低）</h2>
                {!applicantsError && (applicants.length === 0 ? <p>暂无申请人</p> : <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderSpacing: '12px', textAlign: 'left' }}>
                        <thead><tr><th scope="col">候选人</th><th scope="col">技能</th><th scope="col">匹配分</th><th scope="col">申请状态</th><th scope="col">面试预约（UTC）</th></tr></thead>
                        <tbody>{applicants.map(applicant => <ApplicantRow key={applicant.application_id} applicant={applicant} onUpdated={updateStatus} />)}</tbody>
                    </table>
                </div>)}
            </section>
        </>}
    </main>
}

export default JobDetailPage

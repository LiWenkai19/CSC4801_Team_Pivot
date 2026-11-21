import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { changeApplicationStatus, getMyJob, listJobApplicants } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'
import type { ApplicantPublic, ApplicationStatus, JobPublic } from '../../types'

const statuses: ApplicationStatus[] = ['Pending', 'Interviewing', 'Rejected', 'Accepted']

/** 预约按上海时间展示，兼容不带偏移量的 UTC 测试数据。 */
function bookingTime(value: string): string {
    const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
    return new Date(timestamp).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
}

/** 每张申请人卡片独立保存状态，提交失败时保留当前选择。 */
function ApplicantCard({ applicant, onUpdated }: { applicant: ApplicantPublic; onUpdated: (id: string, status: ApplicationStatus) => void }) {
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

    return <li className="panel employer-applicant-card">
        <header className="employer-applicant-heading">
            <div>
                <h3>{applicant.display_name}</h3>
                <p className="employer-applicant-id">候选人 ID {applicant.candidate_id}</p>
            </div>
            <p className="employer-applicant-score">
                <span>匹配分</span>
                <strong>{applicant.match_score}<small> / 100</small></strong>
            </p>
        </header>
        <div className="employer-applicant-body">
            <section className="employer-applicant-section">
                <h4>技能</h4>
                {applicant.skills.length > 0
                    ? <div className="skill-tags">
                        {applicant.skills.map(skill => <span className="skill-tag" key={skill}>{skill}</span>)}
                    </div>
                    : <p className="record-meta">暂无技能</p>}
            </section>
            <section className="employer-applicant-section">
                <h4>申请状态</h4>
                <p className="status-chip">当前状态：{applicant.status}</p>
                <form className="employer-applicant-form" onSubmit={handleSubmit} aria-busy={submitting}>
                    <select aria-label={`${applicant.display_name}的申请状态`} value={selected} disabled={submitting} onChange={event => {
                        const status = statuses.find(value => value === event.target.value)
                        if (status) setSelected(status)
                        setNotice('')
                    }}>
                        {statuses.map(status => <option key={status} value={status}>{status}</option>)}
                    </select>
                    <button type="submit" disabled={submitting}>{submitting ? '保存中...' : '保存状态'}</button>
                </form>
                {error && <p className="feedback" role="alert">{error} <Link to="/employer/jobs">返回职位列表</Link></p>}
                {notice && <p className="feedback" role="status">{notice}</p>}
            </section>
            <section className="employer-applicant-section">
                <h4>面试预约</h4>
                {applicant.booking ? <p className="employer-applicant-time">
                    <time dateTime={applicant.booking.starts_at}>{bookingTime(applicant.booking.starts_at)}</time>
                    {' 至 '}
                    <time dateTime={applicant.booking.ends_at}>{bookingTime(applicant.booking.ends_at)}</time>
                </p> : <p className="record-meta">未预约</p>}
            </section>
        </div>
    </li>
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

    if (!isEmployer) return <main className="work-page"><p className="feedback" role="alert">仅雇主可访问此页面。</p><Link to="/navpage">返回主页</Link></main>
    return <main className="work-page">
        <nav className="page-nav" aria-label="职位详情导航"><Link to="/employer/jobs">返回职位列表</Link></nav>
        <h1>职位详情与申请人</h1>
        {loading && <p className="feedback" role="status">正在加载职位与申请人...</p>}
        {jobError && <p className="feedback" role="alert">{jobError}</p>}
        {applicantsError && <p className="feedback" role="alert">{applicantsError}</p>}
        {!loading && (jobError || applicantsError) && <button type="button" onClick={retryLoad}>重新加载</button>}
        {!loading && job && <>
            <section className="panel employer-job-overview" aria-label="职位信息">
                <header className="section-heading employer-job-heading">
                    <h2>{job.title}</h2>
                    <Link className="button" to={`/employer/jobs/${job.id}/edit`}>编辑职位</Link>
                </header>
                <div className="employer-job-overview-body">
                    <section className="employer-job-content">
                        <h3>职位描述</h3>
                        <p className="description">{job.description}</p>
                    </section>
                    <section className="employer-job-skill-panel">
                        <h3>所需技能</h3>
                        {job.required_skills.length > 0
                            ? <div className="skill-tags">
                                {job.required_skills.map(skill => <span className="skill-tag" key={skill}>{skill}</span>)}
                            </div>
                            : <p className="record-meta">无指定技能</p>}
                    </section>
                </div>
            </section>
            <section className="page-section" aria-label="申请人列表">
                <header className="section-heading">
                    <h2>申请人</h2>
                    <p className="page-intro">按匹配分从高到低排列，面试时间为上海时间（UTC+8）。</p>
                </header>
                {!applicantsError && (applicants.length === 0 ? <p className="panel empty-state">暂无申请人</p> : <ul className="employer-applicant-list" role="list">
                    {applicants.map(applicant => <ApplicantCard key={applicant.application_id} applicant={applicant} onUpdated={updateStatus} />)}
                </ul>)}
            </section>
        </>}
    </main>
}

export default JobDetailPage

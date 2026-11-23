import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { changeApplicationStatus, getMyJob, listJobApplicants } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'
import type { ApplicantPublic, ApplicationStatus, JobPublic } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import type { Locale } from '../../i18n/LanguageContext'
import { apiFeedback } from '../../i18n/apiFeedback'
import { formatShanghaiTime } from '../../i18n/dates'

const statuses: ApplicationStatus[] = ['Pending', 'Interviewing', 'Rejected', 'Accepted']

/** 预约按上海时间展示，兼容不带偏移量的 UTC 测试数据。 */
function bookingTime(value: string, locale: Locale): string {
    const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
    return formatShanghaiTime(timestamp, locale, true)
}

/** 每张申请人卡片独立保存状态，提交失败时保留当前选择。 */
function ApplicantCard({ applicant, onUpdated }: { applicant: ApplicantPublic; onUpdated: (id: string, status: ApplicationStatus) => void }) {
    const { locale, t } = useLanguage()
    const [selected, setSelected] = useState<ApplicationStatus>(applicant.status)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState<MessageKey | ''>('')
    const [notice, setNotice] = useState<MessageKey | ''>('')
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
            setNotice('applications.statusSaved')
        } catch (reason) {
            setError(apiFeedback(reason, 'applications.statusSaveFailed'))
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }

    return <li className="panel employer-applicant-card">
        <header className="employer-applicant-heading">
            <h3>{applicant.display_name}</h3>
            <p className="employer-applicant-score">
                <span>{t('jobs.score')}</span>
                <strong>{applicant.match_score}<small> / 100</small></strong>
            </p>
        </header>
        <div className="employer-applicant-body">
            <section className="employer-applicant-section">
                <h4>{t('applications.skills')}</h4>
                {applicant.skills.length > 0
                    ? <div className="skill-tags">
                        {applicant.skills.map(skill => <span className="skill-tag" key={skill}>{skill}</span>)}
                    </div>
                    : <p className="record-meta">{t('applications.noSkills')}</p>}
            </section>
            <section className="employer-applicant-section">
                <h4>{t('applications.statusTitle')}</h4>
                <p className="status-chip">{t('applications.currentStatus', { status: t(`status.${applicant.status}`) })}</p>
                <form className="employer-applicant-form" onSubmit={handleSubmit} aria-busy={submitting}>
                    <select aria-label={t('applications.statusFor', { name: applicant.display_name })} value={selected} disabled={submitting} onChange={event => {
                        const status = statuses.find(value => value === event.target.value)
                        if (status) setSelected(status)
                        setNotice('')
                    }}>
                        {statuses.map(status => <option key={status} value={status}>{t(`status.${status}`)}</option>)}
                    </select>
                    <button type="submit" disabled={submitting}>{submitting ? t('common.saving') : t('applications.saveStatus')}</button>
                </form>
                {error && <p className="feedback" role="alert">{t(error)} <Link to="/employer/jobs">{t('jobs.backToList')}</Link></p>}
                {notice && <p className="feedback" role="status">{t(notice)}</p>}
            </section>
            <section className="employer-applicant-section">
                <h4>{t('booking.title')}</h4>
                {applicant.booking ? <p className="employer-applicant-time">
                    <time dateTime={applicant.booking.starts_at}>{bookingTime(applicant.booking.starts_at, locale)}</time>
                    {t('common.dateRangeSeparator')}
                    <time dateTime={applicant.booking.ends_at}>{bookingTime(applicant.booking.ends_at, locale)}</time>
                </p> : <p className="record-meta">{t('slots.unbooked')}</p>}
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
    const { t } = useLanguage()
    const { currentUser } = useAuth()
    const isEmployer = currentUser?.role === 'employer'
    const [job, setJob] = useState<JobPublic | null>(null)
    const [applicants, setApplicants] = useState<ApplicantPublic[]>([])
    const [loading, setLoading] = useState(true)
    const [jobError, setJobError] = useState<MessageKey | ''>('')
    const [applicantsError, setApplicantsError] = useState<MessageKey | ''>('')
    const [attempt, setAttempt] = useState(0)

    useEffect(() => {
        if (!isEmployer || !jobId) return
        let active = true
        Promise.allSettled([getMyJob(jobId), listJobApplicants(jobId)]).then(([jobResult, applicantsResult]) => {
            if (!active) return
            if (jobResult.status === 'fulfilled') setJob(jobResult.value)
            else setJobError(apiFeedback(jobResult.reason, 'jobs.detailLoadFailed'))
            if (applicantsResult.status === 'fulfilled') setApplicants(applicantsResult.value)
            else setApplicantsError(apiFeedback(applicantsResult.reason, 'jobs.applicantsLoadFailed'))
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

    if (!isEmployer) return <main className="work-page"><p className="feedback" role="alert">{t('auth.employerOnly')}</p><Link to="/navpage">{t('common.home')}</Link></main>
    return <main className="work-page">
        <nav className="page-nav" aria-label={t('jobs.detailNav')}><Link to="/employer/jobs">{t('jobs.backToList')}</Link></nav>
        <h1>{t('jobs.detailTitle')}</h1>
        {loading && <p className="feedback" role="status">{t('jobs.applicantsLoading')}</p>}
        {jobError && <p className="feedback" role="alert">{t(jobError)}</p>}
        {applicantsError && <p className="feedback" role="alert">{t(applicantsError)}</p>}
        {!loading && (jobError || applicantsError) && <button type="button" onClick={retryLoad}>{t('common.reload')}</button>}
        {!loading && job && <>
            <section className="panel employer-job-overview" aria-label={t('jobs.info')}>
                <header className="section-heading employer-job-heading">
                    <h2>{job.title}</h2>
                    <Link className="button" to={`/employer/jobs/${job.id}/edit`}>{t('jobs.edit')}</Link>
                </header>
                <div className="employer-job-overview-body">
                    <section className="employer-job-content">
                        <h3>{t('jobs.description')}</h3>
                        <p className="description">{job.description}</p>
                    </section>
                    <section className="employer-job-skill-panel">
                        <h3>{t('jobs.requiredSkills')}</h3>
                        {job.required_skills.length > 0
                            ? <div className="skill-tags">
                                {job.required_skills.map(skill => <span className="skill-tag" key={skill}>{skill}</span>)}
                            </div>
                            : <p className="record-meta">{t('jobs.noRequiredSkills')}</p>}
                    </section>
                </div>
            </section>
            <section className="page-section" aria-label={t('jobs.applicantsList')}>
                <header className="section-heading">
                    <h2>{t('jobs.applicants')}</h2>
                    <p className="page-intro">{t('jobs.applicantsIntro')}</p>
                </header>
                {!applicantsError && (applicants.length === 0 ? <p className="panel empty-state">{t('jobs.noApplicants')}</p> : <ul className="employer-applicant-list" role="list">
                    {applicants.map(applicant => <ApplicantCard key={applicant.application_id} applicant={applicant} onUpdated={updateStatus} />)}
                </ul>)}
            </section>
        </>}
    </main>
}

export default JobDetailPage

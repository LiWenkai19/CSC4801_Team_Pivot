import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { changeApplicationStatus, getMyJob, listJobApplicants } from '../../api/employer_api'
import { displaySkillName } from '../../components/skills/skillCatalog'
import { useAuth } from '../../contexts/AuthContext'
import type { ApplicantPublic, ApplicationStatus, JobPublic } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import type { Locale } from '../../i18n/LanguageContext'
import { apiFeedback } from '../../i18n/apiFeedback'
import { formatShanghaiTime } from '../../i18n/dates'
import { ApiError } from '../../api/common_api'
import { isVersionConflict } from '../../i18n/apiFeedback'

const statuses: ApplicationStatus[] = ['Pending', 'Interviewing', 'Rejected', 'Accepted']

/** 预约按上海时间展示，兼容不带偏移量的 UTC 测试数据。 */
function bookingTime(value: string, locale: Locale): string {
    const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
    return formatShanghaiTime(timestamp, locale, true)
}

/** 每张申请人卡片独立保存状态，提交失败时保留当前选择。 */
function ApplicantCard({ applicant, jobId, onUpdated }: { applicant: ApplicantPublic; jobId: string; onUpdated: (id: string, status: ApplicationStatus, version: number) => void }) {
    const { locale, t } = useLanguage()
    const [selected, setSelected] = useState<ApplicationStatus>(applicant.status)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState<MessageKey | ''>('')
    const [notice, setNotice] = useState<MessageKey | ''>('')
    const [conflict, setConflict] = useState(false)
    const [reloading, setReloading] = useState(false)
    const pending = useRef(false)

    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (pending.current || conflict) return
        pending.current = true
        setSubmitting(true)
        setError('')
        setNotice('')
        try {
            const saved = await changeApplicationStatus(applicant.application_id, { status: selected, version: applicant.version })
            onUpdated(saved.application_id, saved.status, saved.version)
            setSelected(saved.status)
            setNotice('applications.statusSaved')
        } catch (reason) {
            if (isVersionConflict(reason)) setConflict(true)
            else setError(apiFeedback(reason, 'applications.statusSaveFailed'))
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }

    async function latestStatus() {
        const rows = await listJobApplicants(jobId)
        const latest = rows.find(row => row.application_id === applicant.application_id)
        if (!latest) throw new ApiError('Application not found', 404)
        return latest
    }

    function applyLatest(latest: ApplicantPublic) {
        onUpdated(latest.application_id, latest.status, latest.version)
        setSelected(latest.status)
        setConflict(false)
        setError('')
        setNotice('edit.refreshed')
    }

    async function reloadLatest() {
        if (pending.current || !window.confirm(t('edit.discardConfirm'))) return
        pending.current = true
        setReloading(true)
        try { applyLatest(await latestStatus()) }
        catch (reason) { setError(apiFeedback(reason, 'common.loadFailed')) }
        finally { pending.current = false; setReloading(false) }
    }

    async function checkForUpdates() {
        if (pending.current) return
        pending.current = true
        setReloading(true)
        setError('')
        setNotice('')
        try {
            const latest = await latestStatus()
            if (latest.version === applicant.version) {
                setNotice('edit.upToDate')
                return
            }
            if (selected !== applicant.status) {
                setConflict(true)
                if (!window.confirm(t('edit.discardConfirm'))) return
            }
            applyLatest(latest)
        } catch (reason) { setError(apiFeedback(reason, 'edit.checkFailed')) }
        finally { pending.current = false; setReloading(false) }
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
                        {applicant.skills.map(skill => <span className="skill-tag" key={skill}>{displaySkillName(skill)}</span>)}
                    </div>
                    : <p className="record-meta">{t('applications.noSkills')}</p>}
            </section>
            <section className="employer-applicant-section">
                <h4>{t('applications.statusTitle')}</h4>
                <p className="status-chip">{t('applications.currentStatus', { status: t(`status.${applicant.status}`) })}</p>
                <form className="employer-applicant-form" onSubmit={handleSubmit} aria-busy={submitting || reloading}>
                    <select aria-label={t('applications.statusFor', { name: applicant.display_name })} value={selected} disabled={submitting || reloading} onChange={event => {
                        const status = statuses.find(value => value === event.target.value)
                        if (status) setSelected(status)
                        setNotice('')
                    }}>
                        {statuses.map(status => <option key={status} value={status}>{t(`status.${status}`)}</option>)}
                    </select>
                    <button type="submit" disabled={submitting || reloading || conflict}>{submitting ? t('common.saving') : t('applications.saveStatus')}</button>
                    <button type="button" disabled={submitting || reloading} onClick={checkForUpdates}><svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginInlineEnd: 6, verticalAlign: 'text-bottom' }}><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /></svg>{reloading ? t('edit.checkingUpdates') : t('edit.checkUpdates')}</button>
                </form>
                {conflict && <div className="feedback" role="alert"><p>{t('edit.conflict')}</p><button type="button" disabled={submitting || reloading} onClick={reloadLatest}>{t('edit.reloadLatest')}</button></div>}
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

    function updateStatus(id: string, status: ApplicationStatus, version: number) {
        setApplicants(previous => previous.map(applicant => applicant.application_id === id ? { ...applicant, status, version } : applicant))
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
                                {job.required_skills.map(skill => <span className="skill-tag" key={skill}>{displaySkillName(skill)}</span>)}
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
                    {applicants.map(applicant => <ApplicantCard key={applicant.application_id} applicant={applicant} jobId={job.id} onUpdated={updateStatus} />)}
                </ul>)}
            </section>
        </>}
    </main>
}

export default JobDetailPage

import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/common_api'
import { deleteJob, listMyJobs } from '../../api/employer_api'
import { displaySkillName } from '../../components/skills/skillCatalog'
import { useAuth } from '../../contexts/AuthContext'
import type { JobPublic } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import type { Message } from '../../i18n/LanguageContext'
import { apiFeedback } from '../../i18n/apiFeedback'

/** 本人职位列表；删除成功才移除记录，冲突时保留原列表。 */
function JobListPage() {
    const { t } = useLanguage()
    const { currentUser } = useAuth()
    const isEmployer = currentUser?.role === 'employer'
    const [jobs, setJobs] = useState<JobPublic[]>([])
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<MessageKey | ''>('')
    const [actionError, setActionError] = useState<MessageKey | ''>('')
    const [notice, setNotice] = useState<Message | ''>('')
    const [deleting, setDeleting] = useState<string | null>(null)
    const [attempt, setAttempt] = useState(0)
    const pending = useRef(false)

    useEffect(() => {
        if (!isEmployer) return
        let active = true
        listMyJobs().then(data => { if (active) setJobs(data) })
            .catch(reason => { if (active) setLoadError(apiFeedback(reason, 'common.loadFailed')) })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [isEmployer, attempt])

    function retryLoad() {
        setLoading(true)
        setLoadError('')
        setAttempt(previous => previous + 1)
    }

    /** 所有权与依赖检查由服务端执行，204 成功后更新页面。 */
    async function handleDelete(job: JobPublic) {
        if (pending.current) return
        pending.current = true
        setDeleting(job.id)
        setActionError('')
        setNotice('')
        try {
            await deleteJob(job.id)
            setJobs(previous => previous.filter(item => item.id !== job.id))
            setNotice({ key: 'jobs.deleted', values: { title: job.title } })
        } catch (reason) {
            setActionError(reason instanceof ApiError && reason.status === 409
                ? 'jobs.deleteConflict'
                : apiFeedback(reason, 'common.deleteFailed'))
        } finally {
            pending.current = false
            setDeleting(null)
        }
    }

    if (!isEmployer) return <main className="work-page"><p className="feedback" role="alert">{t('auth.employerOnly')}</p><Link to="/navpage">{t('common.home')}</Link></main>
    return <main className="work-page">
        <nav className="page-nav" aria-label={t('jobs.manageNav')}>
            <Link to="/navpage">{t('common.home')}</Link>
            <Link to="/employer/company">{t('company.title')}</Link>
            <div className="page-nav-actions">
                <Link className="button" to="/employer/interview-slots">{t('slots.create')}</Link>
                <Link className="button" to="/employer/jobs/new">{t('jobs.new')}</Link>
            </div>
        </nav>
        <h1>{t('jobs.myJobs')}</h1>
        {loading && <p className="feedback" role="status">{t('jobs.loading')}</p>}
        {loadError && <div className="page-section"><p className="feedback" role="alert">{t(loadError)}</p><button type="button" onClick={retryLoad}>{t('common.reload')}</button></div>}
        {actionError && <p className="feedback" role="alert">{t(actionError)}</p>}
        {notice && <p className="feedback" role="status">{t(notice)}</p>}
        {!loading && !loadError && (jobs.length === 0 ? <p className="panel empty-state">{t('jobs.empty')}</p> : <ul className="employer-job-list" role="list">
            {jobs.map(job => <li key={job.id} className="panel employer-job-summary">
                <div className="employer-job-content">
                    <h2>{job.title}</h2>
                    <p className="employer-job-excerpt">{job.description}</p>
                    <div className="skill-tags employer-job-skills">
                        <span className="record-meta">{t('jobs.requiredSkills')}</span>
                        {job.required_skills.length > 0
                            ? job.required_skills.map(skill => <span className="skill-tag" key={skill}>{displaySkillName(skill)}</span>)
                            : <span className="record-meta">{t('jobs.noRequiredSkills')}</span>}
                    </div>
                </div>
                <div className="employer-job-actions">
                    <Link className="button button-primary" to={`/employer/jobs/${job.id}`}>{t('jobs.viewApplicants')}</Link>
                    <Link className="button" to={`/employer/jobs/${job.id}/edit`}>{t('common.edit')}</Link>
                    <button className="button-danger" type="button" disabled={deleting !== null} onClick={() => handleDelete(job)}>{deleting === job.id ? t('common.deleting') : t('common.delete')}</button>
                </div>
            </li>)}
        </ul>)}
    </main>
}

export default JobListPage

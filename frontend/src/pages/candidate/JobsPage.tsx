import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listJobs } from '../../api/candidate_api'
import { displaySkillName } from '../../components/skills/skillCatalog'
import ApplyButton from '../../components/candidate/ApplyButton'
import type { RecommendedJob } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'

/** 服务端提供分数与顺序，页面只展示，不维护第二套排序算法。 */
function JobsPage() {
    const { t } = useLanguage()
    const [jobs, setJobs] = useState<RecommendedJob[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<MessageKey | ''>('')
    const [attempt, setAttempt] = useState(0)
    useEffect(() => {
        let active = true
        listJobs().then(data => { if (active) setJobs(data) })
            .catch(reason => { if (active) setError(apiFeedback(reason, 'jobs.loadFailed')) })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [attempt])
    return <>
        <header className="candidate-heading">
            <h1>{t('jobs.recommended')}</h1>
            <p className="page-intro">{t('jobs.recommendedIntro')}</p>
        </header>
        {loading && <p className="feedback" role="status">{t('jobs.loading')}</p>}
        {error && <div className="record-stack"><p className="feedback" role="alert">{t(error)}</p><div><button type="button" onClick={() => { setError(''); setLoading(true); setAttempt(value => value + 1) }}>{t('common.reload')}</button></div></div>}
        {!loading && !error && (jobs.length === 0 ? <p className="panel empty-state">{t('jobs.recommendedEmpty')}</p> : <section className="job-board" aria-label={t('jobs.recommended')}>
            <div className="job-board-header job-grid" aria-hidden="true">
                <span>{t('jobs.listHeading')} <small>{t('jobs.count', { count: jobs.length })}</small></span>
                <span>{t('jobs.requiredSkills')}</span>
                <span>{t('jobs.skillMatch')}</span>
            </div>
            <ul className="job-results" role="list">
                {jobs.map(job => <li key={job.id} className="recommended-job job-grid">
                    <div className="record-stack">
                        <h2><Link className="record-title" to={`/candidate/jobs/${job.id}`}>{job.title}</Link></h2>
                        <p className="record-meta">{job.company_name}</p>
                    </div>
                    <div className="skill-tags">
                        <span className="job-cell-label">{t('jobs.requiredSkills')}</span>
                        {job.required_skills.length
                            ? job.required_skills.map(skill => <span className="skill-tag" key={skill}>{displaySkillName(skill)}</span>)
                            : <span className="record-meta">{t('jobs.noRequiredSkills')}</span>}
                    </div>
                    <div className="job-score">
                        <span className="job-cell-label">{t('jobs.skillMatch')}</span>
                        <p className="job-score-number">{job.match_score}<small> / 100</small></p>
                        <span className="score-scale" aria-hidden="true"><span style={{ width: `${job.match_score}%` }} /></span>
                    </div>
                    <div className="job-actions">
                        <ApplyButton jobId={job.id} applied={job.applied} />
                        <Link className="button button-primary" to={`/candidate/jobs/${job.id}`}>{t('jobs.view')}</Link>
                    </div>
                </li>)}
            </ul>
        </section>)}
    </>
}

export default JobsPage

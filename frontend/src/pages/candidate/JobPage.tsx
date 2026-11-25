import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getJob } from '../../api/candidate_api'
import { displaySkillName } from '../../components/skills/skillCatalog'
import ApplyButton from '../../components/candidate/ApplyButton'
import type { RecommendedJob } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'

/** 职位详情按 URL 重新加载，旧请求返回时不会覆盖新页面。 */
function JobContent({ jobId }: { jobId: string }) {
    const { t } = useLanguage()
    const [job, setJob] = useState<RecommendedJob | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<MessageKey | ''>('')
    const [attempt, setAttempt] = useState(0)
    useEffect(() => {
        let active = true
        getJob(jobId).then(data => { if (active) setJob(data) })
            .catch(reason => { if (active) setError(apiFeedback(reason, 'jobs.loadFailed')) })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [jobId, attempt])
    return <>
        {loading && <p className="feedback" role="status">{t('jobs.detailLoading')}</p>}
        {error && <div className="page-section"><h1>{t('jobs.unavailable')}</h1><p className="feedback" role="alert">{t(error)}</p><button type="button" onClick={() => { setLoading(true); setError(''); setAttempt(value => value + 1) }}>{t('common.reload')}</button></div>}
        {!loading && !error && job?.id === jobId && <>
            <header className="candidate-heading">
                <h1>{job.title}</h1>
                <p className="page-intro">{t('common.companyValue', { name: job.company_name })}</p>
                {job.company_description.trim() && <p className="page-intro description company-introduction">{job.company_description}</p>}
            </header>
            <section className="panel page-section">
                <p>{t('jobs.scoreLabel')}<strong>{job.match_score} / 100</strong></p>
                <p>{t('jobs.requiredSkillsValue', { skills: job.required_skills.map(displaySkillName).join(', ') || t('common.none') })}</p>
                <h2>{t('jobs.description')}</h2><p className="description">{job.description}</p>
                <ApplyButton key={job.id} jobId={job.id} applied={job.applied} />
            </section>
        </>}
    </>
}

function JobPage() {
    const { jobId = '' } = useParams()
    return <JobContent key={jobId} jobId={jobId} />
}

export default JobPage

import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { createJob, getMyJob, updateJob } from '../../api/employer_api'
import EmployerSkillPicker from '../../components/skills/EmployerSkillPicker'
import { useAuth } from '../../contexts/AuthContext'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback, isVersionConflict } from '../../i18n/apiFeedback'

/** 新建和编辑共用表单；路由变化后重新加载，避免沿用上一职位输入。 */
function JobFormPage() {
    const { jobId } = useParams<{ jobId: string }>()
    return <JobForm key={jobId ?? 'new'} jobId={jobId} />
}

/** 按职位 ID 隔离输入与请求，地址变化后旧响应不会覆盖新表单。 */
function JobForm({ jobId }: { jobId: string | undefined }) {
    const { t } = useLanguage()
    const navigate = useNavigate()
    const { currentUser } = useAuth()
    const isEmployer = currentUser?.role === 'employer'
    const [title, setTitle] = useState('')
    const [description, setDescription] = useState('')
    const [skills, setSkills] = useState<string[]>([])
    const [version, setVersion] = useState<number | null>(null)
    const [conflict, setConflict] = useState(false)
    const [reloading, setReloading] = useState(false)
    const [loading, setLoading] = useState(Boolean(jobId))
    const [loadError, setLoadError] = useState<MessageKey | ''>('')
    const [submitError, setSubmitError] = useState<MessageKey | ''>('')
    const [submitting, setSubmitting] = useState(false)
    const [attempt, setAttempt] = useState(0)
    const pending = useRef(false)

    useEffect(() => {
        if (!isEmployer) return
        let active = true
        if (jobId) {
            getMyJob(jobId).then(job => {
                if (!active) return
                setTitle(job.title)
                setDescription(job.description)
                setSkills(job.required_skills)
                setVersion(job.version)
            }).catch(reason => { if (active) setLoadError(apiFeedback(reason, 'common.loadFailed')) })
                .finally(() => { if (active) setLoading(false) })
        }
        return () => { active = false }
    }, [isEmployer, jobId, attempt])

    function retryLoad() {
        setLoading(true)
        setLoadError('')
        setAttempt(previous => previous + 1)
    }

    /** 技能由选择器维护为数组，空数组表示该职位不限制技能。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (pending.current || loading || loadError || conflict || (jobId && version === null)) return
        setSubmitError('')
        if (!title.trim() || !description.trim()) {
            setSubmitError('jobs.requiredFields')
            return
        }
        const data = {
            title: title.trim(),
            description,
            required_skills: skills,
        }
        pending.current = true
        setSubmitting(true)
        try {
            if (jobId && version !== null) {
                const saved = await updateJob(jobId, { ...data, version })
                setVersion(saved.version)
            }
            else await createJob(data)
            navigate('/employer/jobs')
        } catch (reason) {
            if (isVersionConflict(reason)) setConflict(true)
            else setSubmitError(apiFeedback(reason, 'common.saveFailed'))
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }

    async function reloadLatest() {
        if (!jobId || pending.current || !window.confirm(t('edit.discardConfirm'))) return
        pending.current = true
        setReloading(true)
        try {
            const latest = await getMyJob(jobId)
            setTitle(latest.title)
            setDescription(latest.description)
            setSkills(latest.required_skills)
            setVersion(latest.version)
            setConflict(false)
            setSubmitError('')
        } catch (reason) {
            setSubmitError(apiFeedback(reason, 'common.loadFailed'))
        } finally { pending.current = false; setReloading(false) }
    }

    if (!isEmployer) return <main className="work-page"><p className="feedback" role="alert">{t('auth.employerOnly')}</p><Link to="/navpage">{t('common.home')}</Link></main>
    return <main className="work-page work-page-narrow">
        <nav className="page-nav" aria-label={t('jobs.jobFormNav')}><Link to="/employer/jobs">{t('jobs.backToList')}</Link></nav>
        <h1>{jobId ? t('jobs.edit') : t('jobs.new')}</h1>
        {loading && <p className="feedback" role="status">{t('jobs.loading')}</p>}
        {loadError && <div className="page-section"><p className="feedback" role="alert">{t(loadError)}</p><button type="button" onClick={retryLoad}>{t('common.reload')}</button></div>}
        {!loading && !loadError && <form className="form-panel" onSubmit={handleSubmit} aria-busy={submitting || reloading}>
            <fieldset disabled={submitting || reloading}>
                <legend>{t('jobs.info')}</legend>
                <div className="field">
                    <label htmlFor="job-title">{t('jobs.titleField')}</label>
                    <input id="job-title" value={title} required onChange={event => setTitle(event.target.value)} />
                </div>
                <div className="field">
                    <label htmlFor="job-description">{t('jobs.descriptionField')}</label>
                    <textarea id="job-description" value={description} required rows={6} onChange={event => setDescription(event.target.value)} />
                </div>
                <EmployerSkillPicker value={skills} onChange={setSkills} />
                {conflict && <div className="feedback" role="alert"><p>{t('edit.conflict')}</p><button type="button" onClick={reloadLatest}>{t('edit.reloadLatest')}</button></div>}
                <button type="submit" disabled={conflict}>{submitting ? t('common.saving') : t('jobs.save')}</button>
            </fieldset>
        </form>}
        {submitError && <p className="feedback" role="alert">{t(submitError)}</p>}
    </main>
}

export default JobFormPage

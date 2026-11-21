import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { createJob, getMyJob, updateJob } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'

/** 新建和编辑共用表单；路由变化后重新加载，避免沿用上一职位输入。 */
function JobFormPage() {
    const { jobId } = useParams<{ jobId: string }>()
    return <JobForm key={jobId ?? 'new'} jobId={jobId} />
}

/** 按职位 ID 隔离输入与请求，地址变化后旧响应不会覆盖新表单。 */
function JobForm({ jobId }: { jobId: string | undefined }) {
    const navigate = useNavigate()
    const { currentUser } = useAuth()
    const isEmployer = currentUser?.role === 'employer'
    const [title, setTitle] = useState('')
    const [description, setDescription] = useState('')
    const [skills, setSkills] = useState('')
    const [loading, setLoading] = useState(Boolean(jobId))
    const [loadError, setLoadError] = useState('')
    const [submitError, setSubmitError] = useState('')
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
                setSkills(job.required_skills.join(', '))
            }).catch(reason => { if (active) setLoadError(reason instanceof Error ? reason.message : '加载失败，请重试。') })
                .finally(() => { if (active) setLoading(false) })
        }
        return () => { active = false }
    }, [isEmployer, jobId, attempt])

    function retryLoad() {
        setLoading(true)
        setLoadError('')
        setAttempt(previous => previous + 1)
    }

    /** 空技能输入明确提交 []，使编辑可以清空技能要求。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (pending.current || loading || loadError) return
        setSubmitError('')
        if (!title.trim() || !description.trim()) {
            setSubmitError('标题和描述不能为空或只包含空白。')
            return
        }
        const data = {
            title: title.trim(),
            description,
            required_skills: skills.split(/[,，]/).map(skill => skill.trim()).filter(Boolean),
        }
        pending.current = true
        setSubmitting(true)
        try {
            if (jobId) await updateJob(jobId, data)
            else await createJob(data)
            navigate('/employer/jobs')
        } catch (reason) {
            setSubmitError(reason instanceof Error ? reason.message : '保存失败，请重试。')
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }

    if (!isEmployer) return <main className="work-page"><p className="feedback" role="alert">仅雇主可访问此页面。</p><Link to="/navpage">返回主页</Link></main>
    return <main className="work-page work-page-narrow">
        <nav className="page-nav" aria-label="职位表单导航"><Link to="/employer/jobs">返回职位列表</Link></nav>
        <h1>{jobId ? '编辑职位' : '新建职位'}</h1>
        {loading && <p className="feedback" role="status">正在加载职位...</p>}
        {loadError && <div className="page-section"><p className="feedback" role="alert">{loadError}</p><button type="button" onClick={retryLoad}>重新加载</button></div>}
        {!loading && !loadError && <form className="form-panel" onSubmit={handleSubmit} aria-busy={submitting}>
            <fieldset disabled={submitting}>
                <legend>职位信息</legend>
                <div className="field">
                    <label htmlFor="job-title">标题（必填）</label>
                    <input id="job-title" value={title} required onChange={event => setTitle(event.target.value)} />
                </div>
                <div className="field">
                    <label htmlFor="job-description">描述（必填）</label>
                    <textarea id="job-description" value={description} required rows={6} onChange={event => setDescription(event.target.value)} />
                </div>
                <div className="field">
                    <label htmlFor="job-skills">所需技能（逗号分隔，可留空）</label>
                    <input id="job-skills" value={skills} onChange={event => setSkills(event.target.value)} />
                </div>
                <button type="submit">{submitting ? '保存中...' : '保存职位'}</button>
            </fieldset>
        </form>}
        {submitError && <p className="feedback" role="alert">{submitError}</p>}
    </main>
}

export default JobFormPage

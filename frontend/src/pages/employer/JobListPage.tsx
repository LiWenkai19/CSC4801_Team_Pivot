import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/common_api'
import { deleteJob, listMyJobs } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'
import type { JobPublic } from '../../types'

/** 本人职位列表；删除成功才移除记录，冲突时保留原列表。 */
function JobListPage() {
    const { currentUser } = useAuth()
    const isEmployer = currentUser?.role === 'employer'
    const [jobs, setJobs] = useState<JobPublic[]>([])
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState('')
    const [actionError, setActionError] = useState('')
    const [notice, setNotice] = useState('')
    const [deleting, setDeleting] = useState<string | null>(null)
    const [attempt, setAttempt] = useState(0)
    const pending = useRef(false)

    useEffect(() => {
        if (!isEmployer) return
        let active = true
        listMyJobs().then(data => { if (active) setJobs(data) })
            .catch(reason => { if (active) setLoadError(reason instanceof Error ? reason.message : '加载失败，请重试。') })
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
            setNotice(`已删除职位：${job.title}`)
        } catch (reason) {
            setActionError(reason instanceof ApiError && reason.status === 409
                ? '有申请或面试时段，不能删除'
                : reason instanceof Error ? reason.message : '删除失败，请重试。')
        } finally {
            pending.current = false
            setDeleting(null)
        }
    }

    if (!isEmployer) return <main><p role="alert">仅雇主可访问此页面。</p><Link to="/navpage">返回主页</Link></main>
    return <main style={{ width: '100%', padding: 20, boxSizing: 'border-box', textAlign: 'left' }}>
        <h1>我的职位</h1>
        <nav><Link to="/navpage">返回主页</Link> · <Link to="/employer/company">公司资料</Link> · <Link to="/employer/jobs/new">新建职位</Link></nav>
        {loading && <p role="status">正在加载职位...</p>}
        {loadError && <div><p role="alert">{loadError}</p><button type="button" onClick={retryLoad}>重新加载</button></div>}
        {actionError && <p role="alert">{actionError}</p>}
        {notice && <p role="status">{notice}</p>}
        {!loading && !loadError && (jobs.length === 0 ? <p>暂无职位</p> : <ul>
            {jobs.map(job => <li key={job.id} style={{ margin: '20px 0' }}>
                <h2>{job.title}</h2>
                <p>公司：{job.company_name}</p>
                <p>所需技能：{job.required_skills.join(', ') || '无'}</p>
                <p>创建时间：<time dateTime={job.created_at}>{job.created_at}</time></p>
                <Link to={`/employer/jobs/${job.id}`}>查看详情/申请人</Link> · <Link to={`/employer/jobs/${job.id}/edit`}>编辑</Link> · {' '}
                <button type="button" disabled={deleting !== null} onClick={() => handleDelete(job)}>{deleting === job.id ? '删除中...' : '删除'}</button>
            </li>)}
        </ul>)}
    </main>
}

export default JobListPage

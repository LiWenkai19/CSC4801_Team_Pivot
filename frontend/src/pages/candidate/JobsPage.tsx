import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listJobs } from '../../api/candidate_api'
import ApplyButton from '../../components/candidate/ApplyButton'
import type { RecommendedJob } from '../../types'

/** 服务端提供分数与顺序，页面只展示，不维护第二套排序算法。 */
function JobsPage() {
    const [jobs, setJobs] = useState<RecommendedJob[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [attempt, setAttempt] = useState(0)
    useEffect(() => {
        let active = true
        listJobs().then(data => { if (active) setJobs(data) })
            .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : '职位加载失败。') })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [attempt])
    return <>
        <h1>职位推荐</h1>
        <p>按技能匹配分数从高到低排列。修改技能后，推荐会随之更新。</p>
        {loading && <p role="status">正在加载职位...</p>}
        {error && <div><p role="alert">{error}</p><button type="button" onClick={() => { setError(''); setLoading(true); setAttempt(value => value + 1) }}>重新加载</button></div>}
        {!loading && !error && (jobs.length === 0 ? <p>暂无职位，请稍后再来查看。</p> : <ul className="records">
            {jobs.map(job => <li key={job.id}>
                <h2><Link to={`/candidate/jobs/${job.id}`}>{job.title}</Link></h2>
                <p>公司：{job.company_name}</p><p>匹配分数：{job.match_score} / 100</p>
                <p>所需技能：{job.required_skills.join(', ') || '无'}</p>
                <p><Link to={`/candidate/jobs/${job.id}`}>查看职位描述</Link></p>
                <ApplyButton jobId={job.id} applied={job.applied} />
            </li>)}
        </ul>)}
    </>
}

export default JobsPage

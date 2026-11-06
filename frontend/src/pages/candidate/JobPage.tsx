import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getJob } from '../../api/candidate_api'
import ApplyButton from '../../components/candidate/ApplyButton'
import type { RecommendedJob } from '../../types'

/** 职位详情按 URL 重新加载，旧请求返回时不会覆盖新页面。 */
function JobContent({ jobId }: { jobId: string }) {
    const [job, setJob] = useState<RecommendedJob | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [attempt, setAttempt] = useState(0)
    useEffect(() => {
        let active = true
        getJob(jobId).then(data => { if (active) setJob(data) })
            .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : '职位加载失败。') })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [jobId, attempt])
    return <>
        {loading && <p role="status">正在加载职位...</p>}
        {error && <div><h1>无法读取职位</h1><p role="alert">{error}</p><button type="button" onClick={() => { setLoading(true); setError(''); setAttempt(value => value + 1) }}>重新加载</button></div>}
        {!loading && !error && job?.id === jobId && <>
            <h1>{job.title}</h1><p>公司：{job.company_name}</p>
            <p>匹配分数：{job.match_score} / 100</p><p>所需技能：{job.required_skills.join(', ') || '无'}</p>
            <h2>职位描述</h2><p className="description">{job.description}</p>
            <ApplyButton key={job.id} jobId={job.id} applied={job.applied} />
        </>}
    </>
}

function JobPage() {
    const { jobId = '' } = useParams()
    return <JobContent key={jobId} jobId={jobId} />
}

export default JobPage

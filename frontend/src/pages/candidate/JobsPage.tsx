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
        <header className="candidate-heading">
            <h1>职位推荐</h1>
            <p className="page-intro">按技能匹配分从高到低排列。更新个人技能后，推荐会随之更新。</p>
        </header>
        {loading && <p className="feedback" role="status">正在加载职位...</p>}
        {error && <div className="record-stack"><p className="feedback" role="alert">{error}</p><div><button type="button" onClick={() => { setError(''); setLoading(true); setAttempt(value => value + 1) }}>重新加载</button></div></div>}
        {!loading && !error && (jobs.length === 0 ? <p className="panel empty-state">暂无职位，请稍后再来查看。</p> : <section className="job-board" aria-label="推荐职位">
            <div className="job-board-header job-grid" aria-hidden="true">
                <span>职位 <small>{jobs.length} 个</small></span>
                <span>所需技能</span>
                <span>技能匹配分</span>
            </div>
            <ul className="job-results" role="list">
                {jobs.map(job => <li key={job.id} className="recommended-job job-grid">
                    <div className="record-stack">
                        <h2><Link className="record-title" to={`/candidate/jobs/${job.id}`}>{job.title}</Link></h2>
                        <p className="record-meta">{job.company_name}</p>
                    </div>
                    <div className="skill-tags">
                        <span className="job-cell-label">所需技能</span>
                        {job.required_skills.length
                            ? job.required_skills.map(skill => <span className="skill-tag" key={skill}>{skill}</span>)
                            : <span className="record-meta">无指定技能</span>}
                    </div>
                    <div className="job-score">
                        <span className="job-cell-label">技能匹配分</span>
                        <p className="job-score-number">{job.match_score}<small> / 100</small></p>
                        <span className="score-scale" aria-hidden="true"><span style={{ width: `${job.match_score}%` }} /></span>
                    </div>
                    <div className="job-actions">
                        <ApplyButton jobId={job.id} applied={job.applied} />
                        <Link to={`/candidate/jobs/${job.id}`}>查看职位</Link>
                    </div>
                </li>)}
            </ul>
        </section>)}
    </>
}

export default JobsPage

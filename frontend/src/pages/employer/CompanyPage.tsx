import { useEffect, useRef, useState } from 'react'
import type { MouseEvent, SubmitEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/common_api'
import { getMyCompany, updateMyCompany } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'
import type { CompanyPublic, CompanyUpdate } from '../../types'

/** 查看和就地编辑本人公司资料，失败时保留输入。 */
function CompanyPage() {
    const { currentUser, refreshCurrentUser } = useAuth()
    const navigate = useNavigate()
    const isEmployer = currentUser?.role === 'employer'
    const [company, setCompany] = useState<CompanyPublic | null>(null)
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [loading, setLoading] = useState(true)
    const [submitting, setSubmitting] = useState(false)
    const [missing, setMissing] = useState(false)
    const [error, setError] = useState('')
    const [notice, setNotice] = useState('')
    const [attempt, setAttempt] = useState(0)
    const pending = useRef(false)

    useEffect(() => {
        if (!isEmployer) return
        let active = true
        getMyCompany().then(data => {
            if (!active) return
            setCompany(data)
            setName(data.company_name)
            setDescription(data.company_description)
        }).catch(reason => {
            if (!active) return
            setMissing(reason instanceof ApiError && reason.status === 404)
            setError(reason instanceof Error ? reason.message : '加载失败，请重试。')
        }).finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [isEmployer, attempt])

    function retryLoad() {
        setLoading(true)
        setError('')
        setMissing(false)
        setAttempt(previous => previous + 1)
    }

    /** 资料被移除时先刷新账户状态，让既有补填页正确放行。 */
    async function openProfileCreation(event: MouseEvent<HTMLAnchorElement>) {
        event.preventDefault()
        try {
            await refreshCurrentUser()
            navigate('/employer/details')
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : '无法检查资料状态，请重试。')
        }
    }

    /** 仅发送发生变化的字段；描述空字符串表示清空。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (!company || pending.current) return
        setError('')
        setNotice('')
        if (!name.trim()) {
            setError('请输入公司名称，不能只填写空格。')
            return
        }
        const changes: CompanyUpdate = {}
        if (name !== company.company_name) changes.company_name = name.trim()
        if (description !== company.company_description) changes.company_description = description
        if (Object.keys(changes).length === 0) {
            setNotice('没有需要保存的修改。')
            return
        }
        pending.current = true
        setSubmitting(true)
        try {
            const saved = await updateMyCompany(changes)
            setCompany(saved)
            setName(saved.company_name)
            setDescription(saved.company_description)
            setNotice('已保存')
        } catch (reason) {
            setMissing(reason instanceof ApiError && reason.status === 404)
            setError(reason instanceof Error ? reason.message : '保存失败，请重试。')
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }

    if (!isEmployer) return <main><p role="alert">仅雇主可访问此页面。</p><Link to="/navpage">返回主页</Link></main>
    return <main style={{ maxWidth: 640, width: '100%', margin: '32px auto', padding: 20, boxSizing: 'border-box', textAlign: 'left' }}>
        <h1>公司资料</h1>
        <nav><Link to="/navpage">返回主页</Link> · <Link to="/employer/jobs">职位列表</Link></nav>
        {loading && <p role="status">正在加载公司资料...</p>}
        {error && <p role="alert">{error}</p>}
        {missing && <p>请先填写公司资料。<Link to="/employer/details" onClick={openProfileCreation}>填写公司资料</Link></p>}
        {!loading && !company && !missing && <button type="button" onClick={retryLoad}>重新加载</button>}
        {!loading && company && <form onSubmit={handleSubmit} aria-busy={submitting}>
            <fieldset disabled={submitting} style={{ margin: '16px 0', minWidth: 0 }}>
                <legend>编辑公司资料</legend>
                <p><label htmlFor="company-name">公司名称（必填）</label></p>
                <input id="company-name" value={name} required autoComplete="organization" onChange={event => { setName(event.target.value); setNotice('') }} style={{ width: '100%', boxSizing: 'border-box' }} />
                <p><label htmlFor="company-description">公司描述</label></p>
                <textarea id="company-description" value={description} rows={6} onChange={event => { setDescription(event.target.value); setNotice('') }} style={{ width: '100%', boxSizing: 'border-box' }} />
                <button type="submit">{submitting ? '保存中...' : '保存公司资料'}</button>
            </fieldset>
        </form>}
        {notice && <p role="status">{notice}</p>}
    </main>
}

export default CompanyPage

import { useEffect, useRef, useState } from 'react'
import type { MouseEvent, SubmitEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/common_api'
import { getMyCompany, updateMyCompany } from '../../api/employer_api'
import { useAuth } from '../../contexts/AuthContext'
import type { CompanyPublic, CompanyUpdate } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback, isVersionConflict } from '../../i18n/apiFeedback'

/** 查看和就地编辑本人公司资料，失败时保留输入。 */
function CompanyPage() {
    const { t } = useLanguage()
    const { currentUser, refreshCurrentUser } = useAuth()
    const navigate = useNavigate()
    const isEmployer = currentUser?.role === 'employer'
    const [company, setCompany] = useState<CompanyPublic | null>(null)
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [loading, setLoading] = useState(true)
    const [submitting, setSubmitting] = useState(false)
    const [missing, setMissing] = useState(false)
    const [error, setError] = useState<MessageKey | ''>('')
    const [notice, setNotice] = useState<MessageKey | ''>('')
    const [attempt, setAttempt] = useState(0)
    const [conflict, setConflict] = useState(false)
    const [reloading, setReloading] = useState(false)
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
            setError(apiFeedback(reason, 'common.loadFailed'))
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
            setError(apiFeedback(reason, 'company.checkFailed'))
        }
    }

    /** 仅发送发生变化的字段；描述空字符串表示清空。 */
    async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (!company || pending.current || conflict) return
        setError('')
        setNotice('')
        if (!name.trim()) {
            setError('company.nameRequired')
            return
        }
        const changes: Omit<CompanyUpdate, 'version'> = {}
        if (name !== company.company_name) changes.company_name = name.trim()
        if (description !== company.company_description) changes.company_description = description
        if (Object.keys(changes).length === 0) {
            setNotice('company.noChanges')
            return
        }
        pending.current = true
        setSubmitting(true)
        try {
            const saved = await updateMyCompany({ ...changes, version: company.version })
            setCompany(saved)
            setName(saved.company_name)
            setDescription(saved.company_description)
            setNotice('common.saved')
        } catch (reason) {
            setMissing(reason instanceof ApiError && reason.status === 404)
            if (isVersionConflict(reason)) setConflict(true)
            else setError(apiFeedback(reason, 'common.saveFailed'))
        } finally {
            pending.current = false
            setSubmitting(false)
        }
    }

    function applyLatest(latest: CompanyPublic) {
        setCompany(latest)
        setName(latest.company_name)
        setDescription(latest.company_description)
        setConflict(false)
        setError('')
        setNotice('edit.refreshed')
    }

    async function reloadLatest() {
        if (pending.current || !window.confirm(t('edit.discardConfirm'))) return
        pending.current = true
        setReloading(true)
        try {
            applyLatest(await getMyCompany())
        } catch (reason) {
            setError(apiFeedback(reason, 'common.loadFailed'))
        } finally { pending.current = false; setReloading(false) }
    }

    async function checkForUpdates() {
        if (!company || pending.current) return
        pending.current = true
        setReloading(true)
        setError('')
        setNotice('')
        try {
            const latest = await getMyCompany()
            if (latest.version === company.version) {
                setNotice('edit.upToDate')
                return
            }
            if (name !== company.company_name || description !== company.company_description) {
                setConflict(true)
                if (!window.confirm(t('edit.discardConfirm'))) return
            }
            applyLatest(latest)
        } catch (reason) {
            setError(apiFeedback(reason, 'edit.checkFailed'))
        } finally { pending.current = false; setReloading(false) }
    }

    if (!isEmployer) return <main className="work-page"><p className="feedback" role="alert">{t('auth.employerOnly')}</p><Link to="/navpage">{t('common.home')}</Link></main>
    return <main className="work-page work-page-narrow">
        <nav className="page-nav" aria-label={t('company.nav')}><Link to="/navpage">{t('common.home')}</Link><Link to="/employer/jobs">{t('jobs.list')}</Link></nav>
        <h1>{t('company.title')}</h1>
        {loading && <p className="feedback" role="status">{t('company.loading')}</p>}
        {error && <p className="feedback" role="alert">{t(error)}</p>}
        {missing && <p>{t('api.companyRequired')} <Link to="/employer/details" onClick={openProfileCreation}>{t('onboarding.employerTitle')}</Link></p>}
        {!loading && !company && !missing && <button type="button" onClick={retryLoad}>{t('common.reload')}</button>}
        {!loading && company && <form className="form-panel" onSubmit={handleSubmit} aria-busy={submitting || reloading}>
            <fieldset disabled={submitting || reloading}>
                <legend>{t('company.edit')}</legend>
                <div className="field">
                    <label htmlFor="company-name">{t('company.name')}</label>
                    <input id="company-name" value={name} required autoComplete="organization" onChange={event => { setName(event.target.value); setNotice('') }} />
                </div>
                <div className="field">
                    <label htmlFor="company-description">{t('company.description')}</label>
                    <textarea id="company-description" value={description} rows={6} onChange={event => { setDescription(event.target.value); setNotice('') }} />
                </div>
                {conflict && <div className="feedback" role="alert"><p>{t('edit.conflict')}</p><button type="button" onClick={reloadLatest}>{t('edit.reloadLatest')}</button></div>}
                <div className="editor-actions">
                    <button type="submit" disabled={conflict}>{submitting ? t('common.saving') : t('company.save')}</button>
                    <button type="button" onClick={checkForUpdates}><svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginInlineEnd: 6, verticalAlign: 'text-bottom' }}><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /></svg>{reloading ? t('edit.checkingUpdates') : t('edit.checkUpdates')}</button>
                </div>
            </fieldset>
        </form>}
        {notice && <p className="feedback" role="status">{t(notice)}</p>}
    </main>
}

export default CompanyPage

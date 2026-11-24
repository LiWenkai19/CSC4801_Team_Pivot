import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { getMyProfile, updateMyProfile } from '../../api/candidate_api'
import CandidateSkillPicker from '../../components/skills/CandidateSkillPicker'
import type { CandidateProfilePublic } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback, isVersionConflict } from '../../i18n/apiFeedback'

/** 本人资料编辑；加载失败不覆盖输入，保存成功后使用服务端规范化结果。 */
function ProfilePage() {
    const { t } = useLanguage()
    const [profile, setProfile] = useState<CandidateProfilePublic | null>(null)
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<MessageKey | ''>('')
    const [error, setError] = useState<MessageKey | ''>('')
    const [notice, setNotice] = useState<MessageKey | ''>('')
    const [saving, setSaving] = useState(false)
    const [conflict, setConflict] = useState(false)
    const [reloading, setReloading] = useState(false)
    const [attempt, setAttempt] = useState(0)
    const [editorReset, setEditorReset] = useState(0)
    const pending = useRef(false)
    const baseline = useRef<CandidateProfilePublic | null>(null)
    const form = useRef<HTMLFormElement>(null)
    function edit(changes: Partial<CandidateProfilePublic>) {
        setProfile(previous => previous ? { ...previous, ...changes } : previous)
        setNotice('')
        setError('')
    }
    useEffect(() => {
        let active = true
        getMyProfile().then(data => { if (active) { baseline.current = data; setProfile(data) } })
            .catch(reason => { if (active) setLoadError(apiFeedback(reason, 'profile.loadFailed')) })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [attempt])

    async function save(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (!profile || pending.current || conflict) return
        if (!profile.display_name.trim()) { setError('profile.nameRequired'); return }
        pending.current = true
        setSaving(true)
        setError('')
        setNotice('')
        try {
            const saved = await updateMyProfile({ version: profile.version, display_name: profile.display_name, resume_text: profile.resume_text, skills: profile.skills })
            setProfile(saved)
            baseline.current = saved
            setNotice('profile.saved')
        } catch (reason) {
            if (isVersionConflict(reason)) setConflict(true)
            else setError(apiFeedback(reason, 'common.saveFailed'))
        } finally { pending.current = false; setSaving(false) }
    }

    async function reloadLatest() {
        if (pending.current || !window.confirm(t('edit.discardConfirm'))) return
        pending.current = true
        setReloading(true)
        try {
            const latest = await getMyProfile()
            baseline.current = latest
            setProfile(latest)
            setEditorReset(value => value + 1)
            setConflict(false)
            setError('')
            setNotice('')
        } catch (reason) {
            setError(apiFeedback(reason, 'common.loadFailed'))
        } finally { pending.current = false; setReloading(false) }
    }

    async function checkForUpdates() {
        if (!profile || pending.current) return
        pending.current = true
        setReloading(true)
        setError('')
        setNotice('')
        try {
            const latest = await getMyProfile()
            if (latest.version === profile.version) {
                setNotice('edit.upToDate')
                return
            }
            const original = baseline.current
            const hasChanges = !original || profile.display_name !== original.display_name || profile.resume_text !== original.resume_text
                || JSON.stringify([...profile.skills].sort()) !== JSON.stringify([...original.skills].sort())
                || Boolean(form.current?.querySelector<HTMLInputElement>('.skill-input input')?.value.trim())
            if (hasChanges) {
                setConflict(true)
                if (!window.confirm(t('edit.discardConfirm'))) return
            }
            baseline.current = latest
            setProfile(latest)
            setEditorReset(value => value + 1)
            setConflict(false)
            setNotice('edit.refreshed')
        } catch (reason) {
            setError(apiFeedback(reason, 'edit.checkFailed'))
        } finally { pending.current = false; setReloading(false) }
    }

    return <>
        <h1>{t('profile.title')}</h1>
        {loading && <p className="feedback" role="status">{t('profile.loading')}</p>}
        {loadError && <div className="page-section"><p className="feedback" role="alert">{t(loadError)}</p><button type="button" onClick={() => { setLoadError(''); setLoading(true); setAttempt(value => value + 1) }}>{t('common.reload')}</button></div>}
        {!loading && !loadError && profile && <form ref={form} className="form-panel" onSubmit={save} aria-busy={saving || reloading}>
            <fieldset disabled={saving || reloading}>
                <div className="field">
                    <label htmlFor="display-name">{t('profile.name')}</label>
                    <input id="display-name" required value={profile.display_name} onChange={event => edit({ display_name: event.target.value })} />
                </div>
                <div className="field">
                    <label htmlFor="resume">{t('profile.resume')}</label>
                    <textarea id="resume" rows={10} value={profile.resume_text} onChange={event => edit({ resume_text: event.target.value })} />
                </div>
                <CandidateSkillPicker key={editorReset} value={profile.skills} onChange={skills => edit({ skills })} />
                <p className="page-intro">{t('profile.privacy')}</p>
                {error && <p className="feedback" role="alert">{t(error)}</p>}
                {notice && <p className="feedback" role="status">{t(notice)}</p>}
                {conflict && <div className="feedback" role="alert"><p>{t('edit.conflict')}</p><button type="button" onClick={reloadLatest}>{t('edit.reloadLatest')}</button></div>}
                <div className="editor-actions">
                    <button type="submit" disabled={conflict}>{saving ? t('common.saving') : t('profile.save')}</button>
                    <button type="button" onClick={checkForUpdates}><svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginInlineEnd: 6, verticalAlign: 'text-bottom' }}><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /></svg>{reloading ? t('edit.checkingUpdates') : t('edit.checkUpdates')}</button>
                </div>
            </fieldset>
        </form>}
    </>
}

export default ProfilePage

import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { getMyProfile, updateMyProfile } from '../../api/candidate_api'
import CandidateSkillPicker from '../../components/skills/CandidateSkillPicker'
import type { CandidateProfilePublic } from '../../types'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'

/** 本人资料编辑；加载失败不覆盖输入，保存成功后使用服务端规范化结果。 */
function ProfilePage() {
    const { t } = useLanguage()
    const [profile, setProfile] = useState<CandidateProfilePublic | null>(null)
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<MessageKey | ''>('')
    const [error, setError] = useState<MessageKey | ''>('')
    const [notice, setNotice] = useState<MessageKey | ''>('')
    const [saving, setSaving] = useState(false)
    const [attempt, setAttempt] = useState(0)
    const pending = useRef(false)
    function edit(changes: Partial<CandidateProfilePublic>) {
        setProfile(previous => previous ? { ...previous, ...changes } : previous)
        setNotice('')
        setError('')
    }
    useEffect(() => {
        let active = true
        getMyProfile().then(data => { if (active) setProfile(data) })
            .catch(reason => { if (active) setLoadError(apiFeedback(reason, 'profile.loadFailed')) })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [attempt])

    async function save(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (!profile || pending.current) return
        if (!profile.display_name.trim()) { setError('profile.nameRequired'); return }
        pending.current = true
        setSaving(true)
        setError('')
        setNotice('')
        try {
            const saved = await updateMyProfile({ display_name: profile.display_name, resume_text: profile.resume_text, skills: profile.skills })
            setProfile(saved)
            setNotice('profile.saved')
        } catch (reason) {
            setError(apiFeedback(reason, 'common.saveFailed'))
        } finally { pending.current = false; setSaving(false) }
    }

    return <>
        <h1>{t('profile.title')}</h1>
        {loading && <p className="feedback" role="status">{t('profile.loading')}</p>}
        {loadError && <div className="page-section"><p className="feedback" role="alert">{t(loadError)}</p><button type="button" onClick={() => { setLoadError(''); setLoading(true); setAttempt(value => value + 1) }}>{t('common.reload')}</button></div>}
        {!loading && !loadError && profile && <form className="form-panel" onSubmit={save} aria-busy={saving}>
            <fieldset disabled={saving}>
                <div className="field">
                    <label htmlFor="display-name">{t('profile.name')}</label>
                    <input id="display-name" required value={profile.display_name} onChange={event => edit({ display_name: event.target.value })} />
                </div>
                <div className="field">
                    <label htmlFor="resume">{t('profile.resume')}</label>
                    <textarea id="resume" rows={10} value={profile.resume_text} onChange={event => edit({ resume_text: event.target.value })} />
                </div>
                <CandidateSkillPicker value={profile.skills} onChange={skills => edit({ skills })} />
                <p className="page-intro">{t('profile.privacy')}</p>
                {error && <p className="feedback" role="alert">{t(error)}</p>}
                {notice && <p className="feedback" role="status">{t(notice)}</p>}
                <button type="submit">{saving ? t('common.saving') : t('profile.save')}</button>
            </fieldset>
        </form>}
    </>
}

export default ProfilePage

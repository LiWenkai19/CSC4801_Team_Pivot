import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { getMyProfile, updateMyProfile } from '../../api/candidate_api'
import SkillTagPicker from '../../components/skills/SkillTagPicker'
import type { CandidateProfilePublic } from '../../types'

/** 本人资料编辑；加载失败不覆盖输入，保存成功后使用服务端规范化结果。 */
function ProfilePage() {
    const [profile, setProfile] = useState<CandidateProfilePublic | null>(null)
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState('')
    const [error, setError] = useState('')
    const [notice, setNotice] = useState('')
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
            .catch(reason => { if (active) setLoadError(reason instanceof Error ? reason.message : '资料加载失败。') })
            .finally(() => { if (active) setLoading(false) })
        return () => { active = false }
    }, [attempt])

    async function save(event: SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        if (!profile || pending.current) return
        if (!profile.display_name.trim()) { setError('请输入显示名称。'); return }
        pending.current = true
        setSaving(true)
        setError('')
        setNotice('')
        try {
            const saved = await updateMyProfile({ display_name: profile.display_name, resume_text: profile.resume_text, skills: profile.skills })
            setProfile(saved)
            setNotice('资料已保存，职位推荐会使用最新技能。')
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : '保存失败，请重试。')
        } finally { pending.current = false; setSaving(false) }
    }

    return <>
        <h1>我的资料</h1>
        {loading && <p role="status">正在加载资料...</p>}
        {loadError && <div><p role="alert">{loadError}</p><button type="button" onClick={() => { setLoadError(''); setLoading(true); setAttempt(value => value + 1) }}>重新加载</button></div>}
        {!loading && !loadError && profile && <form onSubmit={save} aria-busy={saving}>
            <fieldset disabled={saving} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
                <label htmlFor="display-name">显示名称（必填）</label>
                <input id="display-name" required value={profile.display_name} onChange={event => edit({ display_name: event.target.value })} />
                <label htmlFor="resume">简历（选填）</label>
                <textarea id="resume" rows={10} value={profile.resume_text} onChange={event => edit({ resume_text: event.target.value })} />
                <SkillTagPicker value={profile.skills} onChange={skills => edit({ skills })} />
                <p>简历仅向你本人及你已投递职位的雇主开放。</p>
                {error && <p role="alert">{error}</p>}
                {notice && <p role="status">{notice}</p>}
                <button type="submit">{saving ? '保存中...' : '保存资料'}</button>
            </fieldset>
        </form>}
    </>
}

export default ProfilePage

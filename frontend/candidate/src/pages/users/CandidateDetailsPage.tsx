import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { ApiError, createCandidateProfile } from '../../api/common_api'
import { useAuth } from '../../contexts/AuthContext'
import type { CandidateProfileCreate } from '../../types'
import CandidateForm from './CandidateForm'

/** 为候选人首次保存资料，支持未完成资料时直接退出登录。 */
function CandidateDetailsPage() {
    const { currentUser, loading, refreshCurrentUser, logout } = useAuth()
    const [submitting, setSubmitting] = useState(false)
    const [submitError, setSubmitError] = useState('')
    const [profileSaved, setProfileSaved] = useState(false)

    /** 保存成功后重新确认状态；检查失败时允许重试，避免再次创建资料。 */
    async function completeProfile() {
        setSubmitting(true)
        setSubmitError('')
        try {
            const user = await refreshCurrentUser()
            if (!user.profile_completed) {
                setSubmitError('暂未确认资料状态，请重新检查。')
            }
        } catch {
            setSubmitError('资料已保存，但暂时无法确认状态，请重新检查。')
        } finally {
            setSubmitting(false)
        }
    }

    /** 提交本人资料，重复创建时改为检查已存在的资料状态。 */
    async function handleSubmit(profile: CandidateProfileCreate) {
        if (submitting) return
        setSubmitting(true)
        setSubmitError('')
        try {
            await createCandidateProfile(profile)
        } catch (error) {
            if (!(error instanceof ApiError && error.status === 409)) {
                setSubmitError(error instanceof TypeError
                    ? '暂时无法保存资料，请检查网络或稍后重试。'
                    : error instanceof Error ? error.message : '保存失败，请重试。')
                setSubmitting(false)
                return
            }
        }
        setProfileSaved(true)
        await completeProfile()
    }

    if (loading) return <p role="status">正在检查登录状态...</p>
    if (!currentUser) return <Navigate to="/login" replace />
    if (currentUser.role !== 'candidate') {
        return <Navigate to="/navpage" replace />
    }
    if (currentUser.profile_completed) return <Navigate to="/candidate/jobs" replace />

    return (
        <main style={{ width: '100%', maxWidth: 560, margin: '40px auto', padding: 20, boxSizing: 'border-box', textAlign: 'left' }}>
            <h2>填写候选人资料</h2>
            <p style={{ marginBottom: 20 }}>填写显示名称即可继续，简历和技能可以稍后补充。</p>
            {profileSaved ? (
                <div>
                    <p role="status">资料已保存，正在确认账户状态。</p>
                    {submitError && <p role="alert" style={{ margin: '12px 0' }}>{submitError}</p>}
                    <button type="button" onClick={completeProfile} disabled={submitting}>
                        {submitting ? '检查中...' : '重新检查'}
                    </button>
                </div>
            ) : (
                <CandidateForm submitting={submitting} submitError={submitError} onSubmit={handleSubmit} />
            )}
            <button type="button" onClick={logout} disabled={submitting} style={{ marginTop: 16 }}>
                退出登录
            </button>
        </main>
    )
}

export default CandidateDetailsPage

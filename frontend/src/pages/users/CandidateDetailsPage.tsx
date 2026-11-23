import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { ApiError, createCandidateProfile } from '../../api/common_api'
import { useAuth } from '../../contexts/AuthContext'
import type { CandidateProfileCreate } from '../../types'
import CandidateForm from './CandidateForm'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'

/** 为候选人首次保存资料，支持未完成资料时直接退出登录。 */
function CandidateDetailsPage() {
    const { t } = useLanguage()
    const { currentUser, loading, refreshCurrentUser, logout } = useAuth()
    const [submitting, setSubmitting] = useState(false)
    const [submitError, setSubmitError] = useState<MessageKey | ''>('')
    const [profileSaved, setProfileSaved] = useState(false)

    /** 保存成功后重新确认状态；检查失败时允许重试，避免再次创建资料。 */
    async function completeProfile() {
        setSubmitting(true)
        setSubmitError('')
        try {
            const user = await refreshCurrentUser()
            if (!user.profile_completed) {
                setSubmitError('onboarding.candidateUnconfirmed')
            }
        } catch {
            setSubmitError('onboarding.candidateCheckFailed')
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
                    ? 'onboarding.candidateNetwork'
                    : apiFeedback(error, 'common.saveFailed'))
                setSubmitting(false)
                return
            }
        }
        setProfileSaved(true)
        await completeProfile()
    }

    if (loading) return <main className="work-page"><p className="feedback" role="status">{t('auth.checking')}</p></main>
    if (!currentUser) return <Navigate to="/login" replace />
    if (currentUser.role !== 'candidate' || currentUser.profile_completed) {
        return <Navigate to="/navpage" replace />
    }

    return (
        <main className="work-page work-page-narrow">
            <h1>{t('onboarding.candidateTitle')}</h1>
            <p className="page-intro">{t('onboarding.candidateIntro')}</p>
            {profileSaved ? (
                <div className="panel page-section">
                    <p className="feedback" role="status">{t('onboarding.candidatePending')}</p>
                    {submitError && <p className="feedback" role="alert">{t(submitError)}</p>}
                    <button type="button" onClick={completeProfile} disabled={submitting}>
                        {submitting ? t('onboarding.checking') : t('onboarding.checkAgain')}
                    </button>
                </div>
            ) : (
                <CandidateForm submitting={submitting} submitError={submitError} onSubmit={handleSubmit} />
            )}
            <button className="button-quiet" type="button" onClick={logout} disabled={submitting}>
                {t('auth.logOut')}
            </button>
        </main>
    )
}

export default CandidateDetailsPage

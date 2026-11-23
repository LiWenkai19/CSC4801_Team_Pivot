import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { ApiError, createEmployerProfile } from '../../api/common_api'
import { useAuth } from '../../contexts/AuthContext'
import type { EmployerProfileCreate } from '../../types'
import EmployerForm from './EmployerForm'
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'

/** 为雇主首次保存公司资料，支持未完成资料时直接退出登录。 */
function EmployerDetailsPage() {
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
                setSubmitError('onboarding.employerUnconfirmed')
            }
        } catch {
            setSubmitError('onboarding.employerCheckFailed')
        } finally {
            setSubmitting(false)
        }
    }

    /** 提交本人的公司资料，重复创建时检查已存在的资料状态。 */
    async function handleSubmit(profile: EmployerProfileCreate) {
        if (submitting) return
        setSubmitting(true)
        setSubmitError('')
        try {
            await createEmployerProfile(profile)
        } catch (error) {
            if (!(error instanceof ApiError && error.status === 409)) {
                setSubmitError(error instanceof TypeError
                    ? 'onboarding.employerNetwork'
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
    if (currentUser.role !== 'employer' || currentUser.profile_completed) {
        return <Navigate to="/navpage" replace />
    }

    return (
        <main className="work-page work-page-narrow">
            <h1>{t('onboarding.employerTitle')}</h1>
            <p className="page-intro">{t('onboarding.employerIntro')}</p>
            {profileSaved ? (
                <div className="panel page-section">
                    <p className="feedback" role="status">{t('onboarding.employerPending')}</p>
                    {submitError && <p className="feedback" role="alert">{t(submitError)}</p>}
                    <button type="button" onClick={completeProfile} disabled={submitting}>
                        {submitting ? t('onboarding.checking') : t('onboarding.checkAgain')}
                    </button>
                </div>
            ) : (
                <EmployerForm submitting={submitting} submitError={submitError} onSubmit={handleSubmit} />
            )}
            <button className="button-quiet" type="button" onClick={logout} disabled={submitting}>
                {t('auth.logOut')}
            </button>
        </main>
    )
}

export default EmployerDetailsPage

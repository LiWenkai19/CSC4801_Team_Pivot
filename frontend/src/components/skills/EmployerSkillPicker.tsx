import { useLanguage } from '../../i18n/LanguageContext'
import SkillTagPicker from './SkillTagPicker'

type Props = {
    value: string[]
    onChange: (skills: string[]) => void
}

/** 雇主职位要求：搜索交互与候选人一致，但用职位语境文案，后续可在此加批量导入。 */
function EmployerSkillPicker({ value, onChange }: Props) {
    const { t } = useLanguage()
    return <SkillTagPicker
        value={value}
        onChange={onChange}
        legend={t('skills.employerLegend')}
        selectedLabel={t('skills.employerSelected')}
        inputLabel={t('skills.employerSearch')}
        addLabel={t('skills.employerAdd')}
        help={t('skills.employerHelp')}
        emptyHint={t('skills.employerNoMatches')}
    />
}

export default EmployerSkillPicker

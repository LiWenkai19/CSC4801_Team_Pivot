import { useLanguage } from '../../i18n/LanguageContext'
import SkillTagPicker from './SkillTagPicker'

type Props = {
    value: string[]
    onChange: (skills: string[]) => void
}

/** 候选人技能选择：资料首次填写与编辑共用，沿用候选人语境文案。 */
function CandidateSkillPicker({ value, onChange }: Props) {
    const { t } = useLanguage()
    return <SkillTagPicker
        value={value}
        onChange={onChange}
        legend={t('skills.optional')}
        selectedLabel={t('skills.selected')}
        inputLabel={t('skills.search')}
        addLabel={t('skills.add')}
        help={t('skills.help')}
        emptyHint={t('skills.noMatches')}
    />
}

export default CandidateSkillPicker

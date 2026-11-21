/** 登录页与工作台使用同一品牌标识。 */
export default function Brand({ showDescription = false }: { showDescription?: boolean }) {
    return <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <span>SkillMatch</span>
        {showDescription && <span className="brand-description">职聘匹配平台</span>}
    </div>
}

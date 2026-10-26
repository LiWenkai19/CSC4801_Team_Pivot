# 【技能匹配】集合用于去重和求交集；空要求固定 100，否则用 // 整数除法计算百分比。返回排序元组时按从左到右比较。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
"""候选人与雇主共用的确定性匹配契约。"""


# 函数 normalize_skills(skills)：把技能去首尾空白、转小写、去空项和去重，让两端比较同一套标准值。
from app.users.service import normalize_skills  # Reuse the team contract.


# 函数 match_score(candidate, required)：按技能交集计算分数；简历不参与计算，整数除法保证向下取整。
def match_score(candidate: list[str], required: list[str]) -> int:
    # 将结果保存在 required_set：转为集合，重复元素只保留一份
    required_set = set(normalize_skills(required))
    # if 判断：根据 not required_set 取得本步所需的值；成立时执行下面缩进的代码
    if not required_set:
        # return 结束本函数并把结果交给调用者：使用固定值 100
        return 100
    # return 结束本函数并把结果交给调用者：用 // 做整数除法，把比例百分数向下取整
    return (
        # 继续完成上面的多行语句：return 结束本函数并把结果交给调用者：用 // 做整数除法，把比例百分数向下取整
        100 * len(set(normalize_skills(candidate)) & required_set) // len(required_set)
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 job_sort_key(row)：生成职位排序依据：分数高的在前，同分按标题和稳定 ID 排序。
def job_sort_key(row: dict) -> tuple:
    # return 结束本函数并把结果交给调用者：组装元组；用于多个排序依据时，从左向右依次比较
    return -row["score"], row["title"].lower(), str(row["id"])


# 函数 applicant_sort_key(row)：生成申请人排序依据：分数高的在前，同分按姓名和稳定 ID 排序。
def applicant_sort_key(row: dict) -> tuple:
    # return 结束本函数并把结果交给调用者：组装元组；用于多个排序依据时，从左向右依次比较
    return -row["score"], row["display_name"].lower(), str(row["candidate_id"])

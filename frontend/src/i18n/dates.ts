import type { Locale } from './LanguageContext'

function shanghaiFormatter(locale: Locale, timeStyle: 'short' | 'medium') {
    return new Intl.DateTimeFormat(locale, {
        timeZone: 'Asia/Shanghai',
        dateStyle: 'medium',
        timeStyle,
        hourCycle: 'h23',
    })
}

const formatters = {
    'zh-CN': { short: shanghaiFormatter('zh-CN', 'short'), medium: shanghaiFormatter('zh-CN', 'medium') },
    'en-US': { short: shanghaiFormatter('en-US', 'short'), medium: shanghaiFormatter('en-US', 'medium') },
}

/** 语言只影响日期和时间的显示格式，预约时间仍按上海时区解释。 */
export function formatShanghaiTime(value: string | Date, locale: Locale, withSeconds = false) {
    const date = typeof value === 'string' ? new Date(value) : value
    return formatters[locale][withSeconds ? 'medium' : 'short'].format(date)
}

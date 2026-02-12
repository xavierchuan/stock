# 线索状态枚举

- `NEW`：新评论线索，尚未私信
- `TRIAL_SENT`：已发送试用包
- `TRIAL_OPENED`：用户确认已打开体验版
- `LIMIT_HIT`：已触发免费版限制（每日3次或仅前3只候选）
- `FOLLOWED_24H`：已完成24小时跟进
- `TRIPWIRE_PAID`：已购买19-39服务单
- `MAIN_PAID`：已购买299主商品
- `LOST`：超过72小时无响应或明确放弃

状态流转建议：

`NEW -> TRIAL_SENT -> TRIAL_OPENED -> LIMIT_HIT -> MAIN_PAID`

`NEW -> TRIAL_SENT -> FOLLOWED_24H -> TRIPWIRE_PAID -> MAIN_PAID`

补充说明：

- `TRIAL_OPENED` 对应字段：`opened_success=1` 或 `trial_opened_at` 有值
- `LIMIT_HIT` 对应字段：`limit_hit=1` 且记录 `limit_hit_at`

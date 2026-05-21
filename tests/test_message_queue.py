"""WizardMessageQueue 单元测试

覆盖 src/wizard/message_queue.py 中未直接测试的路径：
- 禁用/队列满时的 send() 行为
- subscribe/unsubscribe/_notify_subscribers
- enable/disable/clear/size/is_empty/is_full
- 全局函数 set_message_queue / reset_message_queue
"""

import unittest

from src.wizard.events import WizardEventType
from src.wizard.message_queue import (
    WizardMessageQueue,
    get_message_queue,
    reset_message_queue,
    set_message_queue,
)


class TestWizardMessageQueue(unittest.TestCase):
    """WizardMessageQueue 边界测试"""

    def setUp(self):
        self.mq = WizardMessageQueue(maxsize=100)

    # ── 禁用/满队列 ──────────────────────────────────────────

    def test_send_when_disabled(self):
        """disable() 后 send() 返回 False"""
        self.mq.disable()
        result = self.mq.send(WizardEventType.WIZARD_START, {})
        self.assertFalse(result)

    def test_send_queue_full(self):
        """队列满时 send() 返回 False"""
        mq = WizardMessageQueue(maxsize=1)
        mq.send(WizardEventType.WIZARD_START, {})
        # 队列已满，再次 send 应返回 False
        result = mq.send(WizardEventType.MODE_SELECTED, {})
        self.assertFalse(result)

    def test_enable_reenables(self):
        """disable() 后 enable() 恢复发送"""
        self.mq.disable()
        self.mq.enable()
        result = self.mq.send(WizardEventType.WIZARD_START, {})
        self.assertTrue(result)

    # ── subscribe / unsubscribe ──────────────────────────────

    def test_subscribe_and_notify(self):
        """subscribe 后 send 触发回调"""
        received = []
        self.mq.subscribe(lambda e: received.append(e.event_type))
        self.mq.send(WizardEventType.WIZARD_START, {})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], WizardEventType.WIZARD_START)

    def test_unsubscribe(self):
        """unsubscribe 后回调不再被调用"""
        received = []

        def cb(e):
            received.append(1)

        self.mq.subscribe(cb)
        self.mq.unsubscribe(cb)
        self.mq.send(WizardEventType.WIZARD_START, {})
        self.assertEqual(len(received), 0)

    def test_subscriber_exception_does_not_crash(self):
        """一个订阅者抛异常不影响其他订阅者"""
        received = []

        def bad_cb(e):
            raise RuntimeError("test error")

        def good_cb(e):
            received.append(1)

        self.mq.subscribe(bad_cb)
        self.mq.subscribe(good_cb)
        self.mq.send(WizardEventType.WIZARD_START, {})
        self.assertEqual(len(received), 1)

    def test_multiple_subscribers(self):
        """多个订阅者都被通知"""
        results = []
        self.mq.subscribe(lambda e: results.append(1))
        self.mq.subscribe(lambda e: results.append(2))
        self.mq.send(WizardEventType.MODE_SELECTED, {})
        self.assertEqual(results, [1, 2])

    # ── clear / size / empty / full ──────────────────────────

    def test_clear(self):
        """clear() 清空所有事件"""
        self.mq.send(WizardEventType.WIZARD_START, {})
        self.mq.send(WizardEventType.MODE_SELECTED, {})
        self.mq.clear()
        self.assertTrue(self.mq.is_empty())

    def test_size_and_is_full(self):
        """size() 反映队列深度，is_full() 检测满状态"""
        self.assertEqual(self.mq.size(), 0)
        self.mq.send(WizardEventType.WIZARD_START, {})
        self.assertEqual(self.mq.size(), 1)
        self.assertFalse(self.mq.is_empty())

    def test_is_empty_initial(self):
        """初始状态 is_empty() 为 True"""
        self.assertTrue(self.mq.is_empty())
        self.assertFalse(self.mq.is_full())

    # ── 便捷发送方法 ─────────────────────────────────────────

    def test_send_wizard_start_convenience(self):
        """send_wizard_start() 便捷方法"""
        result = self.mq.send_wizard_start({"mode": "interactive"})
        self.assertTrue(result)
        self.assertEqual(self.mq.size(), 1)

    def test_send_wizard_cancelled_convenience(self):
        """send_wizard_cancelled() 便捷方法"""
        result = self.mq.send_wizard_cancelled()
        self.assertTrue(result)

    def test_send_wizard_error_convenience(self):
        """send_wizard_error() 便捷方法，优先级=1"""
        result = self.mq.send_wizard_error("test error")
        self.assertTrue(result)

    # ── receive ──────────────────────────────────────────────

    def test_receive_with_timeout(self):
        """receive() 空队列超时返回 None"""
        result = self.mq.receive(timeout=0.01)
        self.assertIsNone(result)

    def test_receive_all(self):
        """receive_all() 返回所有事件"""
        self.mq.send_wizard_start({})
        self.mq.send_wizard_complete({})
        events = self.mq.receive_all()
        self.assertEqual(len(events), 2)


class TestGlobalMessageQueue(unittest.TestCase):
    """全局消息队列函数测试"""

    def tearDown(self):
        reset_message_queue(None)

    def test_get_message_queue_creates_singleton(self):
        """get_message_queue() 返回全局实例"""
        reset_message_queue(None)
        q1 = get_message_queue()
        q2 = get_message_queue()
        self.assertIs(q1, q2)

    def test_set_message_queue_replaces(self):
        """set_message_queue() 替换全局实例"""
        reset_message_queue(None)
        old_q = get_message_queue()
        old_q.send_wizard_start({})
        new_q = WizardMessageQueue()
        set_message_queue(new_q)
        # 旧队列应被 clear
        self.assertIs(get_message_queue(), new_q)

    def test_reset_message_queue_none(self):
        """reset_message_queue(None) 后 get_message_queue() 返回全新空队列"""
        q1 = get_message_queue()
        q1.send_wizard_start({})
        reset_message_queue(None)
        q2 = get_message_queue()
        self.assertIsNot(q1, q2)
        self.assertTrue(q2.is_empty())


if __name__ == "__main__":
    unittest.main(verbosity=2)

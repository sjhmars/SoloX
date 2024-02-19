from logzero import logger

class Monitor(object):
    def __init__(self, **kwargs):
        self.config = kwargs
        self.matched_data = {}

    def start(self):
        logger.warn("请在%s类中实现start方法" % type(self))

    def clear(self):
        self.matched_data = {}

    def stop(self):
        logger.warning("请在%s类中实现stop方法" % type(self))

    def save(self):
        logger.warning("请在%s类中实现save方法" % type(self))
# -*- coding: utf-8 -*-
from mako import exceptions
from mako.lookup import TemplateLookup
from mako.template import Template
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.web.static import File
from twisted.internet import defer
import os
from twisted.internet.defer import inlineCallbacks


def init_pages(web, coordinator, db):
    web.putChild("yahooweather-show", YWShow(coordinator))
    web.putChild("yahooweather-manage", YWManage(coordinator))
    web.putChild("yahooweather-images", File(os.path.join("houseagent/plugins/yahooweather/templates/images")))


class YWShow(Resource):
    def __init__(self, coordinator):
        Resource.__init__(self)
        self.coordinator = coordinator

    def result(self, result):

        lookup = TemplateLookup(directories=["houseagent/templates/"])
        template = Template(filename="houseagent/plugins/yahooweather/templates/show.html", lookup=lookup, default_filters=['decode.utf8'])

        try:
            self.request.write(str(template.render_unicode(result=result).encode("utf-8", "replace")))
            self.request.finish()
        except:
            self.request.write(exceptions.html_error_template().render())
            self.request.finish()

        return NOT_DONE_YET


    def render_GET(self, request):

        self.request = request
        plugins = self.coordinator.get_plugins_by_type("YahooWeather")

        if len(plugins) == 0:
            self.request.write(str("No online YahooWeather plugins found..."))
            self.request.finish()
        elif len(plugins) == 1:
            self.pluginguid = plugins[0].guid
            self.pluginid = plugins[0].id
            self.coordinator.send_custom(self.pluginguid, "get_forecast", {}).addCallback(self.result)

        return NOT_DONE_YET


class YWManage(Resource):
    def __init__(self, coordinator):
        Resource.__init__(self)
        self.coordinator = coordinator

    def result(self, result):

        lookup = TemplateLookup(directories=["houseagent/templates/"])
        template = Template(filename="houseagent/plugins/yahooweather/templates/manage.html", lookup=lookup, default_filters=['decode.utf8'])

        try:
            self.request.write(str(template.render_unicode(result=result).encode("utf-8", "replace")))
            self.request.finish()
        except:
            self.request.write(exceptions.html_error_template().render())
            self.request.finish()


    def render_GET(self, request):

        self.request = request
        plugins = self.coordinator.get_plugins_by_type("YahooWeather")

        if len(plugins) == 0:
            self.request.write(str("No online YahooWeather plugins found..."))
            self.request.finish()
        elif len(plugins) == 1:
            self.pluginguid = plugins[0].guid
            self.pluginid = plugins[0].id
            self.coordinator.send_custom(self.pluginguid, "get_woeids", {}).addCallback(self.result)

        return NOT_DONE_YET


    def woeid_saved(self, result):
        self.request.write("OK")
        self.request.finish()


    def process_woeids(self, result, new_woeid):

        if int(new_woeid) not in result:
            self.coordinator.send_custom(self.pluginguid, "add_woeid", {"woeid": new_woeid}).addCallback(self.woeid_saved)


    def render_POST(self, request):

        self.request = request
        plugins = self.coordinator.get_plugins_by_type("YahooWeather")

        if len(plugins) == 0:
            self.request.write(str("No online YahooWeather plugins found..."))
            self.request.finish()
        elif len(plugins) == 1:

            _action = request.args["action"][0]
            _woeid = request.args["woeid"][0]

            if _action == "add":
                self.pluginguid = plugins[0].guid
                self.pluginid = plugins[0].id
                self.coordinator.send_custom(self.pluginguid, "get_woeids", {}).addCallback(self.process_woeids, _woeid)

            elif _action == "del":
                self.pluginguid = plugins[0].guid
                self.pluginid = plugins[0].id
                self.coordinator.send_custom(self.pluginguid, "del_woeid", {"woeid":_woeid}).addCallback(self.result)

        return NOT_DONE_YET


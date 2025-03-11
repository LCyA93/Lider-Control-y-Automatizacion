import {UncaughtCorsError} from "@web/core/errors/error_service";
import {registry} from "@web/core/registry";

const errorHandlerRegistry = registry.category("error_handlers");

/* Story here is that there is a bug on Bryntum Gantt:
   https://github.com/bryntum/support/issues/7373
   We've debugged it down to TimeAxisSubGrid which can sometimes throw
   a 'ResizeObserver loop completed with undelivered notifications' error.

   A solution is to call Gantt with monitorResize: false on TimeAxisSubGrid:
   https://forum.bryntum.com/viewtopic.php?p=161822#p161822
   But this actively removes functionality because then the axis does not
   redraw anymore on resize. So that's not preferable.

   The error does not hurt except that since Chrome 132, originalError
   changed from undefined to containing the message, and then Odoo 15.0 does
   not squelch the error:
   https://github.com/OCA/OCB/blob/1552f8ba94ce34aa2684d79c76fe8006f7087f1f/
   addons/web/static/src/core/errors/error_service.js#L109

   As we wait for either a way to fix it ourselves by overriding TimeAxisSubGrid,
   or a fix within Bryntum, or a better way of fixing in Odoo, we squelch all
   unknown CORS errors from popups to console log messages.
*/

function resizeObserverErrorHandler(env, error) {
    if (error instanceof UncaughtCorsError) {
        console.log(
            "Bryntum Gantt caught an unknown CORS error:",
            error.traceback,
            "If you see the text 'Uncaught ResizeObserver', you can safely ignore it."
        );
        return true;
    }
}

errorHandlerRegistry.add("resizeObserverErrorHandler", resizeObserverErrorHandler, {
    sequence: 94,
});

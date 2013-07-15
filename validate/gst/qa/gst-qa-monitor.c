/* GStreamer
 * Copyright (C) 2013 Thiago Santos <thiago.sousa.santos@collabora.com>
 *
 * gst-qa-element-monitor.c - QA Monitor class
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 * Boston, MA 02111-1307, USA.
 */

#include "gst-qa-monitor.h"

/**
 * SECTION:gst-qa-monitor
 * @short_description: Base class that wraps a #GObject for QA checks
 *
 * TODO
 */

enum
{
  PROP_0,
  PROP_OBJECT,
  PROP_RUNNER,
  PROP_QA_PARENT,
  PROP_LAST
};

GST_DEBUG_CATEGORY_STATIC (gst_qa_monitor_debug);
#define GST_CAT_DEFAULT gst_qa_monitor_debug

#define _do_init \
  GST_DEBUG_CATEGORY_INIT (gst_qa_monitor_debug, "qa_monitor", 0, "QA Monitor");
#define gst_qa_monitor_parent_class parent_class
G_DEFINE_ABSTRACT_TYPE_WITH_CODE (GstQaMonitor, gst_qa_monitor,
    G_TYPE_OBJECT, _do_init);

static gboolean gst_qa_monitor_do_setup (GstQaMonitor * monitor);
static void
gst_qa_monitor_get_property (GObject * object, guint prop_id,
    GValue * value, GParamSpec * pspec);
static void
gst_qa_monitor_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec);
static GObject *gst_qa_monitor_constructor (GType type,
    guint n_construct_params, GObjectConstructParam * construct_params);

gboolean gst_qa_monitor_setup (GstQaMonitor * monitor);

static void
gst_qa_monitor_dispose (GObject * object)
{
  GstQaMonitor *monitor = GST_QA_MONITOR_CAST (object);

  g_mutex_clear (&monitor->mutex);

  if (monitor->target)
    g_object_unref (monitor->target);

  G_OBJECT_CLASS (parent_class)->dispose (object);
}

static void
gst_qa_monitor_class_init (GstQaMonitorClass * klass)
{
  GObjectClass *gobject_class;

  gobject_class = G_OBJECT_CLASS (klass);

  gobject_class->get_property = gst_qa_monitor_get_property;
  gobject_class->set_property = gst_qa_monitor_set_property;
  gobject_class->dispose = gst_qa_monitor_dispose;
  gobject_class->constructor = gst_qa_monitor_constructor;

  klass->setup = gst_qa_monitor_do_setup;

  g_object_class_install_property (gobject_class, PROP_OBJECT,
      g_param_spec_object ("object", "Object", "The object to be monitored",
          GST_TYPE_OBJECT, G_PARAM_CONSTRUCT_ONLY | G_PARAM_READWRITE));

  g_object_class_install_property (gobject_class, PROP_RUNNER,
      g_param_spec_object ("qa-runner", "QA Runner", "The QA runner to "
          "report errors to", GST_TYPE_QA_RUNNER,
          G_PARAM_CONSTRUCT_ONLY | G_PARAM_READWRITE));

  g_object_class_install_property (gobject_class, PROP_QA_PARENT,
      g_param_spec_object ("qa-parent", "QA parent monitor", "The QA monitor "
          "that is the parent of this one", GST_TYPE_QA_MONITOR,
          G_PARAM_CONSTRUCT_ONLY | G_PARAM_READWRITE));
}

static GObject *
gst_qa_monitor_constructor (GType type, guint n_construct_params,
    GObjectConstructParam * construct_params)
{
  GstQaMonitor *monitor =
      GST_QA_MONITOR_CAST (G_OBJECT_CLASS (parent_class)->constructor (type,
          n_construct_params,
          construct_params));
  gst_qa_monitor_setup (monitor);
  return (GObject *) monitor;
}

static void
gst_qa_monitor_init (GstQaMonitor * monitor)
{
  g_mutex_init (&monitor->mutex);
}

/**
 * gst_qa_monitor_new:
 * @element: (transfer-none): a #GObject to run QA on
 */
GstQaMonitor *
gst_qa_monitor_new (GObject * object)
{
  GstQaMonitor *monitor = g_object_new (GST_TYPE_QA_MONITOR, "object",
      G_TYPE_OBJECT, object, NULL);

  if (GST_QA_MONITOR_GET_OBJECT (monitor) == NULL) {
    /* setup failed, no use on returning this monitor */
    g_object_unref (monitor);
    return NULL;
  }

  return monitor;
}

static gboolean
gst_qa_monitor_do_setup (GstQaMonitor * monitor)
{
  /* NOP */
  return TRUE;
}

gboolean
gst_qa_monitor_setup (GstQaMonitor * monitor)
{
  GST_DEBUG_OBJECT (monitor, "Starting monitor setup");
  return GST_QA_MONITOR_GET_CLASS (monitor)->setup (monitor);
}

static void
gst_qa_monitor_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec)
{
  GstQaMonitor *monitor;

  monitor = GST_QA_MONITOR_CAST (object);

  switch (prop_id) {
    case PROP_OBJECT:
      g_assert (monitor->target == NULL);
      monitor->target = g_value_dup_object (value);
      break;
    case PROP_RUNNER:
      /* we assume the runner is valid as long as this monitor is,
       * no ref taken */
      monitor->runner = g_value_get_object (value);
      break;
    case PROP_QA_PARENT:
      monitor->parent = g_value_get_object (value);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}

static void
gst_qa_monitor_get_property (GObject * object, guint prop_id,
    GValue * value, GParamSpec * pspec)
{
  GstQaMonitor *monitor;

  monitor = GST_QA_MONITOR_CAST (object);

  switch (prop_id) {
    case PROP_OBJECT:
      g_value_set_object (value, GST_QA_MONITOR_GET_OBJECT (monitor));
      break;
    case PROP_RUNNER:
      g_value_set_object (value, GST_QA_MONITOR_GET_RUNNER (monitor));
      break;
    case PROP_QA_PARENT:
      g_value_set_object (value, GST_QA_MONITOR_GET_PARENT (monitor));
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}

void
gst_qa_monitor_post_error (GstQaMonitor * monitor, GstQaErrorArea area,
    const gchar * message, const gchar * detail)
{
  GstQaErrorReport *report;

  report =
      gst_qa_error_report_new (GST_OBJECT_CAST (GST_QA_MONITOR_GET_OBJECT
          (monitor)), area, message, detail);

  GST_WARNING_OBJECT (monitor, "Received error report %d : %s : %s",
      area, message, detail);
  gst_qa_error_report_printf (report);
  if (GST_QA_MONITOR_GET_RUNNER (monitor)) {
    gst_qa_runner_add_error_report (GST_QA_MONITOR_GET_RUNNER (monitor),
        report);
  } else {
    gst_qa_error_report_free (report);
  }
}
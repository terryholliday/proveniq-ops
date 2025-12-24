
import { WIDGET_REGISTRY } from "./registry";

interface Widget {
    widget_type: string;
    data: any;
    priority: number;
}

interface WidgetRendererProps {
    widgets: Widget[];
}

export function WidgetRenderer({ widgets }: WidgetRendererProps) {
    if (!widgets || widgets.length === 0) {
        return <div className="p-8 text-gray-500 text-center">No widgets available for this asset.</div>;
    }

    return (
        <div className="space-y-6">
            {widgets.map((widget, idx) => {
                const Component = WIDGET_REGISTRY[widget.widget_type];

                if (!Component) {
                    return (
                        <div key={idx} className="p-4 border border-dashed border-gray-700 rounded text-gray-500 text-xs">
                            Unknown Widget Type: {widget.widget_type}
                        </div>
                    );
                }

                return (
                    <div key={idx} className="fade-in">
                        <Component data={widget.data} />
                    </div>
                );
            })}
        </div>
    );
}

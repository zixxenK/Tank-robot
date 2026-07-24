#ifndef __OBJECT_H
#define __OBJECT_H

typedef enum {
	OBJECT_TYPE_ID_TYPE = 0x00,
	OBJECT_TYPE_ID_KEY_EVENT = 0x01,
	OBJECT_TYPE_ID_SBUS_STATUS,
	OBJECT_TYPE_ID_GAMEPAD_STATUS,
}ObjectTypeIDEnum;

typedef struct {
	ObjectTypeIDEnum type_id;
} ObjectTypeDef;



#endif


